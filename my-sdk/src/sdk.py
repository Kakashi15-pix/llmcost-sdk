"""Main SDK client for unified cost tracking."""

from typing import Any, Optional, Dict, Callable
import logging

from pricing import (
    CostInterceptor,
    get_cost_aggregator,
    get_pricing_manager,
    wrap_anthropic_client,
    wrap_openai_client,
    wrap_custom_client,
)

logger = logging.getLogger(__name__)


class CostAnalyticsSDK:
    """
    Unified SDK for LLM cost tracking across providers.
    
    Example:
        sdk = CostAnalyticsSDK()
        sdk.wrap_anthropic_client(client)
        
        # Use client normally, costs tracked automatically
        response = client.messages.create(...)
        
        metrics = sdk.get_metrics()
    """

    def __init__(self, auto_sync_pricing: bool = True):
        """
        Initialize SDK.
        
        Args:
            auto_sync_pricing: Automatically sync pricing from upstream daily
        """
        self.interceptor = CostInterceptor(auto_sync_pricing=auto_sync_pricing)
        self.aggregator = get_cost_aggregator()
        self.pricing_manager = get_pricing_manager()

    def wrap_anthropic_client(self, client: Any) -> Any:
        """
        Wrap Anthropic client to track costs.
        
        Args:
            client: Anthropic() instance
        
        Returns:
            Wrapped client (modified in place)
        
        Example:
            from anthropic import Anthropic
            sdk = CostAnalyticsSDK()
            client = Anthropic()
            client = sdk.wrap_anthropic_client(client)
            response = client.messages.create(...)
        """
        return wrap_anthropic_client(client)

    def wrap_openai_client(self, client: Any) -> Any:
        """
        Wrap OpenAI client to track costs.
        
        Args:
            client: OpenAI() instance
        
        Returns:
            Wrapped client (modified in place)
        
        Example:
            from openai import OpenAI
            sdk = CostAnalyticsSDK()
            client = OpenAI()
            client = sdk.wrap_openai_client(client)
            response = client.chat.completions.create(...)
        """
        return wrap_openai_client(client)

    def wrap_custom_client(
        self,
        client: Any,
        provider: str,
        method_path: str,
        response_to_dict: Optional[Callable[[Any], Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Wrap any provider client method path for tracking.

        Args:
            client: Provider SDK client instance
            provider: Provider identifier (e.g. 'cohere', 'groq', 'mistral')
            method_path: Dotted callable path on client
            response_to_dict: Optional response conversion function
            metadata: Optional static metadata attached to tracked request

        Returns:
            Wrapped client (modified in place)
        """
        return wrap_custom_client(
            client=client,
            provider=provider,
            method_path=method_path,
            response_to_dict=response_to_dict,
            interceptor=self.interceptor,
            static_metadata=metadata,
        )

    def process_response(
        self,
        response: Dict[str, Any],
        provider: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Manually process API response to extract cost.
        
        Args:
            response: API response dict
            provider: Provider name ('anthropic', 'openai', etc.)
            request_id: Optional request tracking ID
            metadata: Optional metadata
        
        Returns:
            Cost breakdown dict or None
        
        Example:
            cost = sdk.process_response(response, provider='anthropic')
        """
        cost_breakdown = self.interceptor.process_response(
            response,
            provider=provider,
            request_id=request_id,
            metadata=metadata,
        )
        
        if cost_breakdown:
            return cost_breakdown.to_dict()
        
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get request buffer size and pending requests (metrics now computed on backend)."""
        return {
            "buffer_size": self.aggregator.get_buffer_size(),
            "pending_requests": len(self.aggregator.get_pending_requests()),
        }

    def get_pending_requests(self) -> list:
        """Get all pending requests awaiting flush to backend."""
        return [r.to_dict() for r in self.aggregator.get_pending_requests()]

    def flush_buffer(self) -> None:
        """Manually flush the request buffer to backend."""
        self.aggregator.flush()
        logger.info("Buffer flushed manually")

    def sync_pricing(self) -> bool:
        """
        Manually trigger pricing sync from upstream.
        
        Returns:
            True if sync successful, False otherwise (uses fallback)
        """
        return self.pricing_manager.sync_from_upstream()

    def get_pricing(self, model: str, provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get pricing for a model."""
        return self.pricing_manager.get_pricing(model, provider=provider)

    def get_pricing_data(self) -> Dict[str, Any]:
        """Get all loaded pricing data."""
        return self.pricing_manager.pricing_data


# Global SDK instance
_sdk_instance = None


def get_sdk(auto_sync_pricing: bool = True) -> CostAnalyticsSDK:
    """Get or create global SDK instance."""
    global _sdk_instance
    if _sdk_instance is None:
        _sdk_instance = CostAnalyticsSDK(auto_sync_pricing=auto_sync_pricing)
    return _sdk_instance
