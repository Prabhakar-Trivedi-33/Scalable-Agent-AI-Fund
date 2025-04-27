import httpx
import json
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
import logging
import asyncio
from functools import wraps
import time
from ..core.config import get_settings
from ..schemas.fund import FundSummary, FundDetail, NavDataPoint, PerformanceMetrics

logger = logging.getLogger(__name__)
settings = get_settings()

def async_cache(ttl_seconds: int = None, max_size: int = None):
    """
    Decorator for caching async function results.
    
    Args:
        ttl_seconds: Time to live in seconds for cache entries
        max_size: Maximum number of items in cache
    """
    def decorator(func):
        cache = {}
        cache_info = {"hits": 0, "misses": 0}
        ttl = ttl_seconds or settings.cache_ttl
        max_items = max_size or settings.cache_max_size
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.enable_cache:
                return await func(*args, **kwargs)
                
            # Create a cache key from arguments
            key_parts = [str(arg) for arg in args]
            key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
            cache_key = f"{func.__name__}:{':'.join(key_parts)}"
            
            # Check if the result is in cache and not expired
            now = time.time()
            if cache_key in cache:
                result, expiry = cache[cache_key]
                if now < expiry:
                    cache_info["hits"] += 1
                    return result
            
            # Call the function and cache the result
            cache_info["misses"] += 1
            result = await func(*args, **kwargs)
            
            # Manage cache size
            if len(cache) >= max_items:
                # Remove oldest item (simple strategy)
                oldest_key = min(cache.items(), key=lambda x: x[1][1])[0]
                del cache[oldest_key]
                
            cache[cache_key] = (result, now + ttl)
            return result
            
        # Add cache info and clear methods to the wrapper
        wrapper.cache_info = lambda: cache_info
        wrapper.cache_clear = lambda: cache.clear()
        return wrapper
    return decorator

class MFAPIRepository:
    """Repository for interacting with the MFAPI.in API."""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or settings.mfapi_base_url
        self.timeout = timeout or settings.mfapi_timeout
        
    async def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """Make a request to the API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}{endpoint}")
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"API request error: {str(e)}")
            raise
            
    @async_cache()
    async def get_all_funds(self) -> List[Dict[str, Any]]:
        """Get list of all funds from the API."""
        try:
            return await self._make_request("")
        except Exception as e:
            logger.error(f"Error fetching all funds: {str(e)}")
            return []
            
    @async_cache()
    async def get_fund(self, scheme_code: str) -> Optional[Dict[str, Any]]:
        """Get fund details by scheme code."""
        try:
            return await self._make_request(f"/{scheme_code}")
        except Exception as e:
            logger.error(f"Error fetching fund details: {str(e)}")
            return None

class MutualFundService:
    """Service for mutual fund operations."""
    
    def __init__(self, repository: MFAPIRepository = None):
        self.repository = repository or MFAPIRepository()
        
    async def search_funds(self, query: str, limit: int = 10) -> List[FundSummary]:
        """
        Search for mutual funds based on query string.
        
        Args:
            query: Search term (fund name, AMC, etc.)
            limit: Maximum number of results
            
        Returns:
            List of FundSummary objects
        """
        try:
            # Since MFAPI doesn't have a direct search endpoint, 
            # we need to fetch all funds and filter them
            all_funds = await self.repository.get_all_funds()
            
            # Filter funds based on query
            filtered_funds = []
            query_terms = query.lower().split()
            
            for fund in all_funds:
                scheme_name = fund.get("schemeName", "").lower()
                # Match if all query terms are in the scheme name
                if all(term in scheme_name for term in query_terms):
                    fund_house = self._extract_fund_house(fund.get("schemeName", ""))
                    category = self._categorize_fund(fund.get("schemeName", ""))
                    
                    filtered_funds.append(
                        FundSummary(
                            scheme_code=fund.get("schemeCode"),
                            scheme_name=fund.get("schemeName"),
                            fund_house=fund_house,
                            category=category
                        )
                    )
                    
                    if len(filtered_funds) >= limit:
                        break
                        
            return filtered_funds
                
        except Exception as e:
            logger.error(f"Error searching funds: {str(e)}")
            return []
    
    async def get_fund_details(self, scheme_code: str, include_nav_data: bool = False) -> Optional[FundDetail]:
        """
        Get detailed information about a specific fund.
        
        Args:
            scheme_code: Fund scheme code
            include_nav_data: Whether to include historical NAV data
            
        Returns:
            FundDetail object or None if not found
        """
        try:
            data = await self.repository.get_fund(scheme_code)
            
            if data and data.get("status") == "SUCCESS":
                fund_data = data.get("meta", {})
                nav_data_raw = data.get("data", [])
                
                # Calculate returns based on NAV data
                returns = self._calculate_returns(nav_data_raw)
                performance = PerformanceMetrics(
                    one_month_return=returns.get("1M"),
                    three_month_return=returns.get("3M"),
                    six_month_return=returns.get("6M"),
                    one_year_return=returns.get("1Y"),
                    three_year_return=returns.get("3Y"),
                    five_year_return=returns.get("5Y")
                )
                
                # Create fund detail
                fund_detail = FundDetail(
                    scheme_code=scheme_code,
                    scheme_name=fund_data.get("scheme_name", ""),
                    fund_house=fund_data.get("fund_house", ""),
                    scheme_type=fund_data.get("scheme_type", ""),
                    scheme_category=fund_data.get("scheme_category", ""),
                    scheme_nav=float(nav_data_raw[0].get("nav", 0)) if nav_data_raw else None,
                    scheme_nav_date=nav_data_raw[0].get("date", "") if nav_data_raw else None,
                    performance=performance
                )
                
                # Add NAV data if requested
                if include_nav_data and nav_data_raw:
                    fund_detail.nav_data = [
                        NavDataPoint(date=item.get("date", ""), nav=float(item.get("nav", 0)))
                        for item in nav_data_raw[:365]  # Limit to last year
                    ]
                        
                return fund_detail
                
            return None
                
        except Exception as e:
            logger.error(f"Error fetching fund details: {str(e)}")
            return None
            
    def _extract_fund_house(self, scheme_name: str) -> str:
        """Extract fund house from scheme name."""
        common_fund_houses = [
            "HDFC", "SBI", "ICICI", "Axis", "Kotak", "Aditya Birla", 
            "Nippon", "DSP", "UTI", "IDFC", "Franklin", "Tata", "Mirae",
            "Invesco", "Canara", "L&T", "Motilal", "Parag Parikh", "Edelweiss"
        ]
        
        for fund_house in common_fund_houses:
            if fund_house in scheme_name:
                return fund_house
                
        return ""
        
    def _categorize_fund(self, scheme_name: str) -> str:
        """Categorize fund based on scheme name."""
        scheme_name_lower = scheme_name.lower()
        
        if any(term in scheme_name_lower for term in ["equity", "large cap", "mid cap", "small cap", "flexi cap"]):
            return "Equity"
        elif any(term in scheme_name_lower for term in ["debt", "bond", "income", "liquid", "gilt"]):
            return "Debt"
        elif any(term in scheme_name_lower for term in ["hybrid", "balanced", "equity savings"]):
            return "Hybrid"
        elif any(term in scheme_name_lower for term in ["retirement", "children", "tax saver", "elss"]):
            return "Solution Oriented"
        else:
            return "Other"
        
    def _calculate_returns(self, nav_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate returns for different time periods."""
        returns = {}
        if not nav_data or len(nav_data) < 2:
            return returns
            
        # Most recent NAV
        latest_nav = float(nav_data[0].get("nav", 0))
        try:
            latest_date = datetime.strptime(nav_data[0].get("date", ""), "%d-%m-%Y")
        except ValueError:
            logger.warning("Invalid date format in NAV data")
            return returns
        
        # Define periods
        periods = {
            "1M": timedelta(days=30),
            "3M": timedelta(days=91),
            "6M": timedelta(days=182),
            "1Y": timedelta(days=365),
            "3Y": timedelta(days=1095),
            "5Y": timedelta(days=1825)
        }
        
        # Calculate returns for each period
        for period_key, period_delta in periods.items():
            target_date = latest_date - period_delta
            
            # Find closest NAV to target date
            closest_nav = None
            min_diff = timedelta(days=365)
            
            for entry in nav_data:
                try:
                    entry_date = datetime.strptime(entry.get("date", ""), "%d-%m-%Y")
                    diff = abs(entry_date - target_date)
                    
                    if diff < min_diff:
                        min_diff = diff
                        closest_nav = float(entry.get("nav", 0))
                except (ValueError, TypeError):
                    continue
                    
            # Calculate return if we found a suitable NAV
            if closest_nav and closest_nav > 0:
                period_return = ((latest_nav - closest_nav) / closest_nav) * 100
                returns[period_key] = round(period_return, 2)
                
        return returns

# Create service instance
mutual_fund_service = MutualFundService()
