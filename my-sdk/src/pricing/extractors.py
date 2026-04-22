"""
Provider-specific usage extraction from API responses.
Client-side extractors only extract usage/model/stop_reason.
Cost computation is handled exclusively by backend orchestrator.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class UsageBreakdown:
    """Extracted usage information from an API response (no cost fields)."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    model: str = ""
    provider: str = ""
    stop_reason: Optional[str] = None
    raw_usage: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "model": self.model,
            "provider": self.provider,
            "stop_reason": self.stop_reason,
            "raw_usage": self.raw_usage,
        }


@dataclass
class CostBreakdown:
    """Full cost breakdown (backend-only). Includes usage + computed costs."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_creation_cost: float = 0.0
    cache_read_cost: float = 0.0
    total_cost: float = 0.0
    model: str = ""
    provider: str = ""
    stop_reason: Optional[str] = None
    raw_usage: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "cache_creation_cost": self.cache_creation_cost,
            "cache_read_cost": self.cache_read_cost,
            "total_cost": self.total_cost,
            "model": self.model,
            "provider": self.provider,
            "stop_reason": self.stop_reason,
            "raw_usage": self.raw_usage,
        }


class CostExtractor(ABC):
    """Base class for provider-specific usage extraction (client-side only)."""

    @abstractmethod
    def extract_usage(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract usage fields from API response.
        
        Returns:
            Dict with 'input_tokens', 'output_tokens', 'cache_*_tokens' keys
            or None if extraction failed.
        """
        pass

    @abstractmethod
    def extract_model(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract model name from API response."""
        pass


class AnthropicExtractor(CostExtractor):
    """Anthropic API response cost extraction."""

    def extract_usage(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract usage from Anthropic /v1/messages response.
        
        Response structure:
        {
            "usage": {
                "input_tokens": int,
                "output_tokens": int,
                "cache_creation_input_tokens": int (optional),
                "cache_read_input_tokens": int (optional)
            },
            ...
        }
        """
        try:
            if "usage" not in response:
                logger.warning("No usage field in Anthropic response")
                return None

            usage_obj = response["usage"]
            return {
                "input_tokens": usage_obj.get("input_tokens", 0),
                "output_tokens": usage_obj.get("output_tokens", 0),
                "cache_creation_tokens": usage_obj.get("cache_creation_input_tokens", 0),
                "cache_read_tokens": usage_obj.get("cache_read_input_tokens", 0),
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to extract usage from Anthropic response: {e}")
            return None

    def extract_model(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract model from Anthropic response."""
        return response.get("model")

    def extract_stop_reason(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract stop reason from Anthropic response."""
        return response.get("stop_reason")


class OpenAIExtractor(CostExtractor):
    """OpenAI API response cost extraction."""

    def extract_usage(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract usage from OpenAI response.
        
        Response structure:
        {
            "usage": {
                "prompt_tokens": int,
                "completion_tokens": int,
                "cached_prompt_tokens": int (optional)
            },
            ...
        }
        """
        try:
            if "usage" not in response:
                logger.warning("No usage field in OpenAI response")
                return None

            usage_obj = response["usage"]
            return {
                "input_tokens": usage_obj.get("prompt_tokens", 0),
                "output_tokens": usage_obj.get("completion_tokens", 0),
                "cache_read_tokens": usage_obj.get("cached_prompt_tokens", 0),
                "cache_creation_tokens": 0,  # OpenAI doesn't separately track cache creation
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to extract usage from OpenAI response: {e}")
            return None

    def extract_model(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract model from OpenAI response."""
        return response.get("model")


# Provider registry
EXTRACTORS: Dict[str, type] = {
    "anthropic": AnthropicExtractor,
    "openai": OpenAIExtractor,
}


def get_extractor(provider: str) -> Optional[CostExtractor]:
    """Return an extractor instance for the given provider."""
    extractor_cls = EXTRACTORS.get(provider.lower()) if provider else None
    if not extractor_cls:
        return None
    return extractor_cls()

