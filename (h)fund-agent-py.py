from typing import Dict, List, Any, Tuple, AsyncIterator
from langgraph.graph import StateGraph, END
from langchain.schema import AIMessage, HumanMessage
import logging
from .nodes import (
    analyze_query,
    search_funds,
    fetch_fund_details,
    analyze_funds,
    generate_final_response
)

logger = logging.getLogger(__name__)

class FundAdvisorAgent:
    """Agent for mutual fund advice and analysis."""
    
    def __init__(self):
        self.graph = self._create_graph()
        self.compiled_graph = self.graph.compile()
        
    def _create_graph(self) -> StateGraph:
        """
        Create the fund agent workflow graph.
        
        Returns:
            StateGraph: The configured workflow graph
        """
        # Define the workflow graph
        graph = StateGraph(name="FundAdvisorAgent")
        
        # Add nodes
        graph.add_node("analyze_query", analyze_query)
        graph.add_node("search_funds", search_funds)
        graph.add_node("fetch_fund_details", fetch_fund_details)
        graph.add_node("analyze_funds", analyze_funds)
        graph.add_node("generate_final_response", generate_final_response)
        
        # Define the workflow
        graph.add_edge("analyze_query", "search_funds")
        graph.add_edge("search_funds", "fetch_fund_details")
        graph.add_edge("fetch_fund_details", "analyze_funds")
        graph.add_edge("analyze_funds", "generate_final_response")
        graph.add_edge("generate_final_response", END)
        
        # Set entry point
        graph.set_entry_point("analyze_query")
        
        return graph
        
    async def process_query(self, query: str, chat_history: List[Dict[str, Any]] = None) -> str:
        """
        Process a user query through the fund agent.
        
        Args:
            query: User query about mutual funds
            chat_history: Optional chat history for context
            
        Returns:
            str: Agent's response
        """
        try:
            # Initialize state
            state = {
                "query": query,
                "chat_history": chat_history or []
            }
            
            # Run the agent
            result = await self.compiled_graph.ainvoke(state)
            
            return result.get("response", "I couldn't generate a response. Please try again.")
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return "I encountered an error while processing your query. Please try again."

    async def process_query_stream(self, query: str, chat_history: List[Dict[str, Any]] = None) -> AsyncIterator[str]:
        """
        Process a user query and stream the response.
        
        Args:
            query: User query about mutual funds
            chat_history: Optional chat history for context
            
        Yields:
            str: Chunks of the agent's response
        """
        try:
            # Initialize state
            state = {
                "query": query,
                "chat_history": chat_history or []
            }
            
            # Define node completion messages
            node_messages = {
                "analyze_query": "Analyzing your query about mutual funds...\n\n",
                "search_funds": "Searching for relevant mutual funds...\n\n",
                "fetch_fund_details": "Fetching detailed fund information...\n\n",
                "analyze_funds": "Analyzing fund performance and characteristics...\n\n",
                "generate_final_response": "Preparing your personalized response...\n\n"
            }
            
            # Stream the agent execution
            async for event in self.compiled_graph.astream(state):
                # Handle different event types
                if event["type"] == "on_chain_start":
                    node_name = event["name"]
                    if node_name in node_messages:
                        yield node_messages[node_name]
                        
                elif event["type"] == "on_chain_end" and event["name"] == "generate_final_response":
                    if "response" in event["data"]:
                        yield event["data"]["response"]
                        
        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            yield "I encountered an error while processing your query. Please try again."

# Create singleton instance
fund_advisor_agent = FundAdvisorAgent()

# Convenience functions
async def process_query(query: str, chat_history: List[Dict[str, Any]] = None) -> str:
    """Process a user query through the fund agent."""
    return await fund_advisor_agent.process_query(query, chat_history)

async def process_query_stream(query: str, chat_history: List[Dict[str, Any]] = None) -> AsyncIterator[str]:
    """Process a user query and stream the response."""
    async for chunk in fund_advisor_agent.process_query_stream(query, chat_history):
        yield chunk
