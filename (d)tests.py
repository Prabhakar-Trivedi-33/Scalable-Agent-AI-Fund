
import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.mfapi_service import MFAPIService
from app.agents.fund_agent import run_fund_agent

@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    with TestClient(app) as client:
        yield client

@pytest.fixture
def mock_mfapi_service():
    """Create a mock for the MFAPIService"""
    with patch("app.services.mfapi_service.MFAPIService") as mock:
        # Mock instance methods
        instance = mock.return_value
        instance.search_funds_by_name = AsyncMock()
        instance.get_fund_details = AsyncMock()
        instance.compare_funds = AsyncMock()
        
        # Load sample data
        with open("tests/data/sample_fund.json", "r") as f:
            sample_fund = json.load(f)
        
        with open("tests/data/sample_search.json", "r") as f:
            sample_search = json.load(f)
            
        with open("tests/data/sample_comparison.json", "r") as f:
            sample_comparison = json.load(f)
        
        # Configure mocks
        instance.get_fund_details.return_value = sample_fund
        instance.search_funds_by_name.return_value = sample_search
        instance.compare_funds.return_value = sample_comparison
        
        yield instance

@pytest.fixture
def mock_llm():
    """Create a mock for the LLM client"""
    with patch("app.core.llm.get_llm") as mock:
        # Mock the invoke method
        mock_llm_instance = mock.return_value
        mock_llm_instance.invoke = AsyncMock()
        mock_llm_instance.invoke.return_value.content = "This is a mock LLM response."
        
        yield mock_llm_instance

@pytest.fixture
def mock_fund_agent():
    """Create a mock for the fund agent"""
    with patch("app.agents.fund_agent.run_fund_agent") as mock:
        mock.return_value = {
            "summary": "This is a mock agent response.",
            "details": {
                "question_type": "DETAILS",
                "search_terms": ["HDFC Top 100"],
                "fund_codes": [119010],
                "error": None
            }
        }
        yield mock

import pytest

@pytest.mark.asyncio
async def test_health_check(client):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_search_funds(client, mock_mfapi_service):
    """Test the search funds endpoint"""
    response = client.get("/api/funds/search?q=hdfc")
    assert response.status_code == 200
    assert len(response.json()) > 0

@pytest.mark.asyncio
async def test_fund_details(client, mock_mfapi_service):
    """Test the fund details endpoint"""
    response = client.get("/api/funds/119010")
    assert response.status_code == 200
    assert response.json()["scheme_code"] == 119010

@pytest.mark.asyncio
async def test_compare_funds(client, mock_mfapi_service):
    """Test the compare funds endpoint"""
    response = client.post(
        "/api/funds/compare",
        json={"scheme_codes": [119010, 120465], "period": "1y"}
    )
    assert response.status_code == 200
    assert "funds" in response.json()
    assert "performance" in response.json()

@pytest.mark.asyncio
async def test_ai_query(client, mock_fund_agent):
    """Test the AI query endpoint"""
    response = client.post(
        "/api/ai/query",
        json={"question": "Tell me about HDFC Top 100 fund"}
    )
    assert response.status_code == 200
    assert "summary" in response.json()
    assert "details" in response.json()

import pytest
from httpx import Response
from unittest.mock import AsyncMock, patch

from app.services.mfapi_service import MFAPIService

@pytest.mark.asyncio
async def test_search_funds_by_name():
    """Test searching funds by name"""
    with patch("httpx.AsyncClient.get") as mock_get:
        # Configure the mock
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "schemeCode": 119010,
                "schemeName": "HDFC Top 100 Fund-Growth Option",
                "fundHouse": "HDFC Mutual Fund"
            }
        ]
        mock_get.return_value = mock_response
        
        # Execute test
        service = MFAPIService()
        results = await service.search_funds_by_name("HDFC Top 100")
        
        # Assertions
        assert len(results) == 1
        assert results[0].scheme_code == 119010
        assert results[0].scheme_name == "HDFC Top 100 Fund-Growth Option"
        assert results[0].fund_house == "HDFC Mutual Fund"

@pytest.mark.asyncio
async def test_get_fund_details():
    """Test getting fund details"""
    with patch("httpx.AsyncClient.get") as mock_get:
        # Configure the mock
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {
                "scheme_name": "HDFC Top 100 Fund-Growth Option",
                "scheme_category": "Equity: Large Cap",
                "scheme_type": "Open Ended",
                "fund_house": "HDFC Mutual Fund"
            },
            "data": [
                {
                    "date": "2023-04-21",
                    "nav": "845.123"
                },
                {
                    "date": "2023-04-20",
                    "nav": "840.456"
                }
            ],
            "status": "SUCCESS"
        }
        mock_get.return_value = mock_response
        
        # Execute test
        service = MFAPIService()
        result = await service.get_fund_details(119010)
        
        # Assertions
        assert result.scheme_code == 119010
        assert result.scheme_name == "HDFC Top 100 Fund-Growth Option"
        assert result.scheme_category == "Equity: Large Cap"
        assert result.nav == 845.123
        assert len(result.historical_data) == 2

@pytest.mark.asyncio
async def test_compare_funds():
    """Test comparing funds"""
    with patch.object(MFAPIService, "get_fund_details") as mock_get_details:
        # Configure the mocks
        fund1 = AsyncMock()
        fund1.scheme_code = 119010
        fund1.scheme_name = "HDFC Top 100 Fund-Growth Option"
        fund1.historical_data = [
            {"date": "2023-04-21", "nav": 845.123},
            {"date": "2022-04-21", "nav": 800.000}
        ]
        fund1.dict = lambda: {
            "scheme_code": 119010,
            "scheme_name": "HDFC Top 100 Fund-Growth Option",
            "historical_data": [
                {"date": "2023-04-21", "nav": 845.123},
                {"date": "2022-04-21", "nav": 800.000}
            ]
        }
        
        fund2 = AsyncMock()
        fund2.scheme_code = 120465
        fund2.scheme_name = "ICICI Bluechip Fund-Growth"
        fund2.historical_data = [
            {"date": "2023-04-21", "nav": 65.789},
            {"date": "2022-04-21", "nav": 60.000}
        ]
        fund2.dict = lambda: {
            "scheme_code": 120465,
            "scheme_name": "ICICI Bluechip Fund-Growth",
            "historical_data": [
                {"date": "2023-04-21", "nav": 65.789},
                {"date": "2022-04-21", "nav": 60.000}
            ]
        }
        
        # Set up the mock to return different values for different arguments
        mock_get_details.side_effect = lambda code: fund1 if code == 119010 else fund2
        
        # Execute test
        service = MFAPIService()
        result = await service.compare_funds([119010, 120465], "1y")
        
        # Assertions
        assert len(result["funds"]) == 2
        assert "performance" in result
        assert result["period"] == "1y"

import pytest
from unittest.mock import patch, AsyncMock

from app.agents.nodes import (
    AgentState, 
    question_router,
    fund_searcher, 
    fund_details_fetcher,
    fund_comparator,
    summarizer
)
from app.agents.fund_agent import build_fund_agent, run_fund_agent

@pytest.mark.asyncio
async def test_question_router():
    """Test the question router node"""
    with patch("app.agents.nodes.get_llm") as mock_get_llm:
        # Configure mock
        mock_llm = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.content = "SEARCH"
        mock_llm.invoke = AsyncMock(return_value=mock_resp)
        mock_get_llm.return_value = mock_llm
        
        # Execute test
        state = AgentState(question="Which large cap mutual funds performed best in the last 1 year?")
        result = await question_router(state)
        
        # Assertions
        assert result.question_type == "SEARCH"

@pytest.mark.asyncio
async def test_fund_searcher():
    """Test the fund searcher node"""
    with patch("app.agents.nodes.get_llm") as mock_get_llm, \
         patch("app.agents.nodes.MFAPIService") as mock_service_class:
        # Configure LLM mock
        mock_llm = AsyncMock()
        mock_resp = AsyncMock()
        mock_resp.content = "Search terms: HDFC Top 100"
        mock_llm.invoke = AsyncMock(return_value=mock_resp)
        mock_get_llm.return_value = mock_llm
        
        # Configure service mock
        mock_service = AsyncMock()
        mock_service.search_funds_by_name = AsyncMock(return_value=[
            {"scheme_code": 119010, "scheme_name": "HDFC Top 100 Fund-Growth Option"}
        ])
        mock_service_class.return_value = mock_service
        
        # Execute test
        state = AgentState(question="Tell me about HDFC Top 100 fund", question_type="DETAILS")
        result = await fund_searcher(state)
        
        # Assertions
        assert "HDFC Top 100" in result.search_terms
        assert 119010 in result.fund_codes

@pytest.mark.asyncio
async def test_build_fund_agent():
    """Test building the fund agent graph"""
    # Just verify it builds without errors
    agent = build_fund_agent()
    assert agent is not None

@pytest.mark.asyncio
async def test_run_fund_agent():
    """Test running the fund agent"""
    with patch("app.agents.fund_agent.build_fund_agent") as mock_build_agent:
        # Configure mock graph
        mock_graph = AsyncMock()
        mock_result = AgentState(
            question="Tell me about HDFC Top 100 fund",
            question_type="DETAILS",
            search_terms=["HDFC Top 100"],
            fund_codes=[119010],
            answer="HDFC Top 100 is a large cap fund with good performance."
        )
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        mock_build_agent.return_value = mock_graph
        
        # Execute test
        result = await run_fund_agent("Tell me about HDFC Top 100 fund")
        
        # Assertions
        assert result["summary"] == "HDFC Top 100 is a large cap fund with good performance."
        assert result["details"]["question_type"] == "DETAILS"
