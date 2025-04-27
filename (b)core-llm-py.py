from typing import Dict, Any, Optional, List, Union, Protocol
from langchain.chat_models import ChatOpenAI
from langchain.schema import BaseMessage
import logging
from abc import ABC, abstractmethod
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, messages: List[BaseMessage], temperature: float = 0.1) -> str:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    def get_streaming_model(self, callbacks: Optional[List] = None) -> Any:
        """Get a model instance that supports streaming."""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLM provider."""
    
    def __init__(self, model_name: str = None, api_key: str = None):
        self.model_name = model_name or settings.default_model
        self.api_key = api_key or settings.openai_api_key
        
    def _create_model(self, temperature: float = 0.1, streaming: bool = False, 
                      callbacks: Optional[List] = None) -> ChatOpenAI:
        """Create and configure a ChatOpenAI instance."""
        return ChatOpenAI(
            model=self.model_name,
            temperature=temperature,
            api_key=self.api_key,
            streaming=streaming,
            callbacks=callbacks,
            verbose=settings.app_env == "development"
        )
    
    async def generate(self, messages: List[BaseMessage], temperature: float = 0.1) -> str:
        """Generate a response from the LLM."""
        try:
            llm = self._create_model(temperature=temperature)
            response = await llm.agenerate([messages])
            return response.generations[0][0].text
        except Exception as e:
            logger.error(f"Error generating LLM response: {str(e)}")
            raise
            
    def get_streaming_model(self, callbacks: Optional[List] = None) -> ChatOpenAI:
        """Get a model instance that supports streaming."""
        return self._create_model(
            temperature=settings.default_temperature, 
            streaming=True, 
            callbacks=callbacks
        )

class LLMFactory:
    """Factory for creating LLM provider instances."""
    
    @staticmethod
    def create_provider(provider_type: str = "openai", **kwargs) -> LLMProvider:
        """Create an LLM provider based on type."""
        if provider_type.lower() == "openai":
            return OpenAIProvider(**kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_type}")

# Create default LLM provider
default_llm_provider = LLMFactory.create_provider()

async def generate_response(messages: List[BaseMessage], temperature: float = None) -> str:
    """
    Generate a response from the default LLM provider.
    
    Args:
        messages: List of conversation messages
        temperature: Creativity level of the model (optional)
        
    Returns:
        str: Generated response
    """
    temp = temperature if temperature is not None else settings.default_temperature
    return await default_llm_provider.generate(messages, temperature=temp)
