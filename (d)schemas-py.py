from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union

class QueryRequest(BaseModel):
    """User query request model."""
    query: str = Field(..., description="User query about mutual funds")
    max_results: Optional[int] = Field(5, description="Maximum number of results to return")
    include_historical_data: Optional[bool] = Field(False, description="Whether to include historical NAV data")
    
    @validator('query')
    def validate_query(cls, v):
        """Ensure query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()
    
    @validator('max_results')
    def validate_max_results(cls, v):
        """Ensure max_results is within reasonable bounds."""
        if v is not None and (v < 1 or v > 10):
            return 5  # Default to 5 if out of bounds
        return v
        
    class Config:
        schema_extra = {
            "example": {
                "query": "What are the best large cap equity funds in the last 3 years?",
                "max_results": 5,
                "include_historical_data": False
            }
        }

class ComparisonRequest(BaseModel):
    """Fund comparison request model."""
    fund_ids: List[str] = Field(..., description="List of fund scheme codes to compare")
    comparison_period: Optional[str] = Field("1Y", description="Time period for comparison (1M, 3M, 6M, 1Y, 3Y, 5Y)")
    
    @validator('fund_ids')
    def validate_fund_ids(cls, v):
        """Ensure we have 2-3 fund IDs to compare."""
        if len(v) < 2:
            raise ValueError("At least 2 fund IDs are required for comparison")
        if len(v) > 3:
            return v[:3]  # Limit to 3 funds
        return v
    
    @validator('comparison_period')
    def validate_period(cls, v):
        """Ensure period is valid."""
        valid_periods = ["1M", "3M", "6M", "1Y", "3Y", "5Y"]
        if v not in valid_periods:
            return "1Y"  # Default to 1Y if invalid
        return v
        
    class Config:
        schema_extra = {
            "example": {
                "fund_ids": ["119551", "118560"],
                "comparison_period": "3Y"
            }
        }

class ChatHistoryRequest(BaseModel):
    """Chat history for contextual queries."""
    messages: List[dict] = Field(..., description="Previous messages in the conversation")
    query: str = Field(..., description="Current user query")
    
    class Config:
        schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "I'm looking for equity mutual funds"},
                    {"role": "assistant", "content": "I can help you find equity mutual funds. What specific criteria are you looking for?"}
                ],
                "query": "Show me large cap funds with good returns in the last 3 years"
            }
        }
