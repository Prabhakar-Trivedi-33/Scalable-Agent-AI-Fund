from typing import Dict, List, Any, Tuple, Optional
import json
import re
import logging
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from ..services.mfapi_service import mutual_fund_service
from ..core.llm import generate_response
from .prompts import (
    QUERY_ANALYSIS_PROMPT,
    FUND_SEARCH_PROMPT,
    FUND_ANALYSIS_PROMPT,
    FUND_COMPARISON_PROMPT,
    FINAL_RESPONSE_PROMPT
)

logger = logging.getLogger(__name__)

class QueryAnalyzer:
    """Class for analyzing user queries about mutual funds."""
    
    @staticmethod
    def extract_fund_names(analysis: str) -> List[str]:
        """Extract fund names from query analysis."""
        fund_names = []
        
        # Look for fund names in the analysis
        lines = analysis.split('\n')
        for line in lines:
            if "fund" in line.lower() and ":" in line:
                name_part = line.split(':', 1)[1].strip()
                if name_part and name_part.lower() not in ["none", "not mentioned", "not specified"]:
                    fund_names.append(name_part)
        
        return fund_names
        
    @staticmethod
    def parse_search_terms(search_terms_text: str) -> List[str]:
        """Parse search terms from LLM response."""
        # Try to find a list in the text
        list_match = re.search(r'\[(.+?)\]', search_terms_text, re.DOTALL)
        
        if list_match:
            # Extract terms from list format
            terms_text = list_match.group(1)
            terms = re.findall(r'"([^"]+)"', terms_text)
            
            if not terms:
                terms = re.findall(r"'([^']+)'", terms_text)
                
            if not terms:
                terms = [term.strip() for term in terms_text.split(',')]
                
            return [term for term in terms if term and term.strip()]
        else:
            # Fallback: split by newlines or commas
            if '\n' in search_terms_text:
                return [term.strip() for term in search_terms_text.split('\n') if term.strip()]
            else:
                return [term.strip() for term in search_terms_text.split(',') if term.strip()]
                
    @staticmethod
    def is_comparison_query(query: str) -> bool:
        """Determine if the query is asking for a comparison."""
        comparison_keywords = [
            "compare", "comparison", "versus", "vs", "vs.", 
            "better", "difference", "differences", "which is better",
            "contrast", "against"
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in comparison_keywords)

# Initialize analyzer
query_analyzer = QueryAnalyzer()

async def analyze_query(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze the user query to understand intent and extract key information.
    
    Args:
        state: Current state containing user query
        
    Returns:
        Updated state with query analysis
    """
    query = state["query"]
    chat_history = state.get("chat_history", [])
    
    try:
        # Prepare prompt
        messages = QUERY_ANALYSIS_PROMPT.format_messages(
            query=query
        )
        
        # Generate analysis
        analysis = await generate_response(messages)
        
        # Extract fund names if mentioned
        fund_names = query_analyzer.extract_fund_names(analysis)
        
        # Update state
        return {
            **state,
            "query_analysis": analysis,
            "fund_names": fund_names,
            "chat_history": chat_history + [
                HumanMessage(content=query),
                AIMessage(content="I'm analyzing your query about mutual funds.")
            ]
        }
    except Exception as e:
        logger.error(f"Error in query analysis: {str(e)}")
        return {
            **state,
            "error": f"Query analysis failed: {str(e)}",
            "chat_history": chat_history + [
                HumanMessage(content=query)
            ]
        }

async def search_funds(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for funds based on the query analysis.
    
    Args:
        state: Current state containing query and analysis
        
    Returns:
        Updated state with search results
    """
    query = state["query"]
    chat_history = state.get("chat_history", [])
    fund_names = state.get("fund_names", [])
    
    try:
        # If specific funds were mentioned, search for them
        search_results = []
        
        if fund_names:
            for fund_name in fund_names:
                results = await mutual_fund_service.search_funds(fund_name, limit=5)
                search_results.extend(results)
        else:
            # Generate search terms
            messages = FUND_SEARCH_PROMPT.format_messages(
                query=query,
                chat_history=chat_history
            )
            search_terms_text = await generate_response(messages)
            
            # Parse search terms
            try:
                search_terms = query_analyzer.parse_search_terms(search_terms_text)
                
                # Search for each term
                for term in search_terms:
                    results = await mutual_fund_service.search_funds(term, limit=5)
                    search_results.extend(results)
            except Exception as e:
                logger.warning(f"Error parsing search terms: {str(e)}")
                # Fallback: search using the original query
                search_results = await mutual_fund_service.search_funds(query, limit=10)
        
        # Deduplicate results
        unique_results = {result.scheme_code: result for result in search_results}
        
        return {
            **state, 
            "search_results": list(unique_results.values()),
            "chat_history": chat_history + [
                AIMessage(content=f"I found {len(unique_results)} funds that match your query.")
            ]
        }
    except Exception as e:
        logger.error(f"Error in fund search: {str(e)}")
        return {
            **state,
            "error": f"Fund search failed: {str(e)}",
            "search_results": [],
            "chat_history": chat_history
        }

async def fetch_fund_details(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch detailed information for the funds found.
    
    Args:
        state: Current state containing search results
        
    Returns:
        Updated state with fund details
    """
    search_results = state.get("search_results", [])
    chat_history = state.get("chat_history", [])
    
    try:
        # Get details for top funds (limit to 3 to avoid rate limiting)
        fund_details = []
        
        max_funds = min(len(search_results), 3)
        
        if max_funds == 0:
            return {
                **state,
                "fund_details": [],
                "chat_history": chat_history + [
                    AIMessage(content="I couldn't find any relevant funds to analyze.")
                ]
            }
        
        for fund in search_results[:max_funds]:
            details = await mutual_fund_service.get_fund_details(
                fund.scheme_code, 
                include_nav_data=True
            )
            if details:
                fund_details.append(details)
        
        return {
            **state,
            "fund_details": fund_details,
            "chat_history": chat_history + [
                AIMessage(content=f"I've gathered detailed information on {len(fund_details)} funds.")
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching fund details: {str(e)}")
        return {
            **state,
            "error": f"Fund details fetch failed: {str(e)}",
            "fund_details": [],
            "chat_history": chat_history
        }

async def analyze_funds(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze fund data based on user query.
    
    Args:
        state: Current state containing fund details
        
    Returns:
        Updated state with fund analysis
    """
    query = state["query"]
    fund_details = state.get("fund_details", [])
    chat_history = state.get("chat_history", [])
    
    if not fund_details:
        return {
            **state,
            "response": "I couldn't find any mutual funds matching your query. Could you please provide more specific information?",
            "chat_history": chat_history + [
                AIMessage(content="I couldn't find any mutual funds matching your query.")
            ]
        }
    
    try:
        # Check if this is a comparison query
        if len(fund_details) >= 2 and query_analyzer.is_comparison_query(query):
            # Compare top 2 funds
            messages = FUND_COMPARISON_PROMPT.format_messages(
                query=query,
                fund_data_1=json.dumps(fund_details[0].dict(), indent=2),
                fund_data_2=json.dumps(fund_details[1].dict(), indent=2),
                chat_history=chat_history
            )
            
            analysis = await generate_response(messages)
            
        else:
            # Analyze single fund
            messages = FUND_ANALYSIS_PROMPT.format_messages(
                query=query,
                fund_data=json.dumps(fund_details[0].dict(), indent=2),
                chat_history=chat_history
            )
            
            analysis = await generate_response(messages)
        
        return {
            **state,
            "fund_analysis": analysis,
            "chat_history": chat_history + [
                AIMessage(content="I've analyzed the fund data based on your query.")
            ]
        }
    except Exception as e:
        logger.error(f"Error in fund analysis: {str(e)}")
        return {
            **state,
            "error": f"Fund analysis failed: {str(e)}",
            "fund_analysis": "I couldn't analyze the fund data due to a technical error.",
            "chat_history": chat_history
        }

async def generate_final_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate the final comprehensive response.
    
    Args:
        state: Current state containing all analysis
        
    Returns:
        Updated state with final response
    """
    query = state["query"]
    chat_history = state.get("chat_history", [])
    fund_analysis = state.get("fund_analysis", "")
    error = state.get("error")
    
    # If there was an error, return a fallback response
    if error and not fund_analysis:
        return {
            **state,
            "response": "I'm sorry, I couldn't complete the analysis of mutual funds based on your query. Please try again with more specific details or check if the fund names are correct.",
            "chat_history": chat_history + [
                AIMessage(content="I couldn't complete the analysis of mutual funds.")
            ]
        }
    
    try:
        context = fund_analysis
        
        # Generate final response
        messages = FINAL_RESPONSE_PROMPT.format_messages(
            query=query,
            context=context,
            chat_history=chat_history
        )
        
        response = await generate_response(messages, temperature=0.3)
        
        return {
            **state,
            "response": response,
            "chat_history": chat_history + [
                AIMessage(content=response)
            ]
        }
    except Exception as e:
        logger.error(f"Error generating final response: {str(e)}")
        # Provide the fund analysis directly if final formatting fails
        return {
            **state,
            "response": fund_analysis or "I'm sorry, I couldn't generate a response based on your query.",
            "chat_history": chat_history + [
                AIMessage(content="Here's what I found about the mutual funds you asked about.")
            ]
        }
