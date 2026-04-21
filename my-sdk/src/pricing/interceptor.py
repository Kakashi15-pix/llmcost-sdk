"""
Interceptor middleware for LLM client libraries.
Extracts cost information from API responses without modifying request/response.
"""
from typing import Any, Callable, Optional, Dict
import logging
import uuid

from pricing.manager import get_pricing_manager
from pricing.extractors import get_extractor, CostBreakdown
from pricing.aggregator import get_cost_aggregator

logger = logging.getLogger(__name__)


class CostInterceptor:
    """
    Intercepts LLM API responses to extract and compute costs.
    Works with signal-plus-pull model: credentials never leave client.
    """

    def __init__(self, auto_sync_pricing: bool = True):
        self.pricing_manager = get_pricing_manager()
        self.aggregator = get_cost_aggregator()
        self.auto_sync_pricing = auto_sync_pricing

    def sync_pricing(self) -> None:
        """Sync pricing from upstream (silent fallback on failure)."""
        if not self.auto_sync_pricing:
            return
        self.pricing_manager.sync_from_upstream()

    def process_response(
        self,
        response: Dict[str, Any],
        provider: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[CostBreakdown]:
        """
        Process API response to extract and record request details.
        Cost computation is deferred to backend.
        
        Args:
            response: API response dict from provider
            provider: Provider name ('anthropic', 'openai', etc.)
            request_id: Optional request tracking ID
            metadata: Optional metadata to attach to request
        
        Returns:
            CostBreakdown with extracted details (cost fields not populated), or None if extraction failed
        """
        if not response:
            return None

        # Get provider-specific extractor
        extractor = get_extractor(provider)
        if not extractor:
            logger.error(f"No extractor for provider: {provider}")
            return None

        # Extract usage
        usage = extractor.extract_usage(response)
        if not usage:
            logger.warning(f"Failed to extract usage from {provider} response")
            return None

        # Extract model
        model = extractor.extract_model(response)
        if not model:
            logger.warning("Failed to extract model from response")
            return None

        # Create cost breakdown for return (note: cost fields are 0)
        cost_breakdown = CostBreakdown(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_tokens", 0),
            cache_read_tokens=usage.get("cache_read_tokens", 0),
            model=model,
            provider=provider,
            raw_usage=usage,
        )

        # Extract stop reason if available
        if hasattr(extractor, 'extract_stop_reason'):
            cost_breakdown.stop_reason = extractor.extract_stop_reason(response)

        # Record request details to buffer (cost computation deferred to backend)
        request_id = request_id or str(uuid.uuid4())
        self.aggregator.record_request(
            request_id=request_id,
            model=model,
            provider=provider,
            input_tokens=cost_breakdown.input_tokens,
            output_tokens=cost_breakdown.output_tokens,
            cache_read_tokens=cost_breakdown.cache_read_tokens,
            cache_creation_tokens=cost_breakdown.cache_creation_tokens,
            stop_reason=cost_breakdown.stop_reason,
            metadata=metadata,
        )

        logger.debug(
            f"Recorded request details for {provider}/{model}: "
            f"({cost_breakdown.input_tokens} in, {cost_breakdown.output_tokens} out, "
            f"{cost_breakdown.cache_read_tokens} cache_read, {cost_breakdown.cache_creation_tokens} cache_creation)"
        )

        return cost_breakdown


class AnthropicInterceptor(CostInterceptor):
    """Interceptor specifically for Anthropic client library."""

    def __call__(self, response: Any) -> Any:
        """
        Decorator/callable for wrapping Anthropic responses.
        
        Usage:
            interceptor = AnthropicInterceptor()
            
            # Wrap existing client
            client = Anthropic()
            original_message = client.messages.create
            
            def wrapped_create(*args, **kwargs):
                resp = original_message(*args, **kwargs)
                interceptor.process_response(resp.model_dump(), 'anthropic')
                return resp
            
            client.messages.create = wrapped_create
        """
        return self

    def wrap_client(self, client: Any) -> Any:
        """
        Wrap Anthropic client to intercept API calls.
        
        Args:
            client: anthropic.Anthropic() instance
        
        Returns:
            Wrapped client (modified in place)
        """
        original_create = client.messages.create

        def wrapped_create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            
            # Extract response data
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            else:
                response_dict = response.__dict__
            
            # Process for cost
            self.process_response(
                response_dict,
                provider='anthropic',
                metadata={'method': 'messages.create'},
            )
            
            return response

        client.messages.create = wrapped_create
        return client


class OpenAIInterceptor(CostInterceptor):
    """Interceptor specifically for OpenAI client library."""

    def wrap_client(self, client: Any) -> Any:
        """
        Wrap OpenAI client to intercept API calls.
        
        Args:
            client: openai.OpenAI() instance
        
        Returns:
            Wrapped client (modified in place)
        """
        original_create = client.chat.completions.create

        def wrapped_create(*args, **kwargs):
            response = original_create(*args, **kwargs)
            
            # Extract response data
            if hasattr(response, 'model_dump'):
                response_dict = response.model_dump()
            else:
                response_dict = response.__dict__
            
            # Process for cost
            self.process_response(
                response_dict,
                provider='openai',
                metadata={'method': 'chat.completions.create'},
            )
            
            return response

        client.chat.completions.create = wrapped_create
        return client


def wrap_anthropic_client(client: Any) -> Any:
    """Convenience function to wrap Anthropic client."""
    interceptor = AnthropicInterceptor()
    return interceptor.wrap_client(client)


def wrap_openai_client(client: Any) -> Any:
    """Convenience function to wrap OpenAI client."""
    interceptor = OpenAIInterceptor()
    return interceptor.wrap_client(client)
