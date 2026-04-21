"""
Interceptor middleware for LLM client libraries.
Forwards request/response details to backend where extraction and cost computation happen.
"""
from typing import Any, Optional, Dict
import logging
import uuid

from pricing.manager import get_pricing_manager
from pricing.extractors import CostBreakdown
from pricing.aggregator import get_cost_aggregator

logger = logging.getLogger(__name__)


class CostInterceptor:

    def __init__(self, auto_sync_pricing: bool = True):
        self.pricing_manager = get_pricing_manager()
        self.aggregator = get_cost_aggregator()
        self.auto_sync_pricing = auto_sync_pricing

    def sync_pricing(self) -> None:
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
        Extraction and cost computation are handled by backend.
        
        Args:
            response: API response dict from provider
            provider: Provider name ('anthropic', 'openai', etc.)
            request_id: Optional request tracking ID
            metadata: Optional metadata to attach to request
        
        Returns:
            CostBreakdown placeholder (no local extraction/cost computation),
            or None if request could not be recorded.
        """
        if not response:
            return None

        request_id = request_id or str(uuid.uuid4())
        request_metadata: Dict[str, Any] = dict(metadata or {})
        request_metadata["raw_response"] = response
        request_metadata["backend_extraction"] = True

        # Keep lightweight local fields for observability only.
        model = response.get("model", "unknown")
        stop_reason = response.get("stop_reason")

        # Placeholder object returned for compatibility with existing API.
        cost_breakdown = CostBreakdown(
            input_tokens=0,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            model=model,
            provider=provider,
            stop_reason=stop_reason,
            raw_usage={"backend_extraction": True},
        )

        # Record request details for backend extraction/costing.
        self.aggregator.record_request(
            request_id=request_id,
            model=model,
            provider=provider,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            stop_reason=stop_reason,
            metadata=request_metadata,
        )

        logger.debug(
            f"Recorded request {request_id} for backend extraction "
            f"({provider}/{model})"
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
