from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
import logging
import json
import asyncio

from ..schemas.fund import FundSummary, FundDetail, FundAnalysis, FundComparison
from ..schemas.request import QueryRequest, ComparisonRequest, ChatHistoryRequest
from ..services.mfapi_service import mutual_fund_service
from ..agents.fund_agent import process_query, process_query_stream

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/funds/search", response_model=List[FundSummary])
async def search_funds(
    q: str = Query(..., description="Search query for mutual funds"),
    limit: int = Query(10, description="Maximum number of results")
):
    """
    Search for mutual funds based on query string.
    """
    try:
        results = await mutual_fund_service.search_funds(q, limit=limit)
        return results
    except Exception as e:
        logger.error(f"Error searching funds: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search funds")

@router.get("/funds/{scheme_code}", response_model=FundDetail)
async def get_fund_details(
    scheme_code: str,
    include_nav_data: bool = Query(False, description="Include historical NAV data")
):
    """
    Get detailed information about a specific mutual fund.
    """
    try:
        fund = await mutual_fund_service.get_fund_details(scheme_code, include_nav_data)
        if not fund:
            raise HTTPException(status_code=404, detail=f"Fund with scheme code {scheme_code} not found")
        return fund
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching fund details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch fund details")

@router.post("/funds/compare", response_model=FundComparison)
async def compare_funds(request: ComparisonRequest):
    """
    Compare multiple mutual funds.
    """
    try:
        # Fetch details for each fund
        funds = []
        for scheme_code in request.fund_ids:
            fund = await mutual_fund_service.get_fund_details(scheme_code, include_nav_data=True)
            if fund:
                funds.append(fund)
                
        if len(funds) < 2:
            raise HTTPException(status_code=404, detail="Couldn't find enough funds to compare")
            
        # Format comparison query
        fund_names = [fund.scheme_name for fund in funds]
        comparison_query = f"Compare {' vs '.join(fund_names)} for {request.comparison_period} period"
        
        # Process through the agent
        response = await process_query(comparison_query)
        
        # Create comparison object
        comparison = FundComparison(
            funds=funds,
            comparison_period=request.comparison_period,
            summary=response[:200],  # Extract summary from response
            performance_comparison=response,
            recommendation=None  # Will be extracted by a more sophisticated parser
        )
        
        return comparison
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing funds: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to compare funds")

@router.post("/query")
async def query_funds(request: QueryRequest):
    """
    Process a natural language query about mutual funds.
    """
    try:
        response = await process_query(request.query)
        return {"response": response}
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process query")

@router.post("/query/stream")
async def query_funds_stream(request: QueryRequest):
    """
    Process a natural language query and stream the response.
    """
    async def generate():
        try:
            async for chunk in process_query_stream(request.query):
                # Format for SSE
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as e:
            logger.error(f"Error in streaming response: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream"
    )

@router.post("/chat")
async def chat(request: ChatHistoryRequest):
    """
    Process a query with chat history for context.
    """
    try:
        # Convert chat history to format expected by the agent
        chat_history = []
        for msg in request.messages:
            if msg["role"] == "user":
                chat_history.append({"type": "human", "content": msg["content"]})
            elif msg["role"] == "assistant":
                chat_history.append({"type": "ai", "content": msg["content"]})
        
        response = await process_query(request.query, chat_history)
        return {"response": response}
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat")
