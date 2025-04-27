from pydantic import BaseSettings, Field
from typing import Optional, Dict, Any
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application configuration settings."""
    
    # API Keys
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    
    # Application Settings
    app_env: str = Field(default=os.getenv("APP_ENV", "development"))
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    
    # MFAPI Configuration
    mfapi_base_url: str = "https://api.mfapi.in/mf"
    mfapi_timeout: int = 30
    
    # Cache Settings
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1 hour
    cache_max_size: int = 1000  # Maximum number of items in cache
    
    # LLM Settings
    default_model: str = "gpt-4-turbo"
    default_temperature: float = 0.1
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration as a dictionary."""
        return {
            "enabled": self.enable_cache,
            "ttl": self.cache_ttl,
            "max_size": self.cache_max_size
        }

@lru_cache()
def get_settings() -> Settings:
    """Create and cache settings instance to avoid multiple instantiations."""
    return Settings()

# Create settings instance for direct import
settings = get_settings()
