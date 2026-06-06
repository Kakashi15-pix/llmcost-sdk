"""Cost analytics and pricing module."""

try:
    from pricing.manager import (  # type: ignore[import-not-found]
        PricingManager,
        BackendPricingOrchestrator,
        get_pricing_manager,
        get_backend_pricing_orchestrator,
    )
except ModuleNotFoundError:
    PricingManager = None
    BackendPricingOrchestrator = None

    def get_pricing_manager():
        raise RuntimeError("pricing.manager is not available in this workspace snapshot")

    def get_backend_pricing_orchestrator(*args, **kwargs):
        raise RuntimeError("pricing.manager is not available in this workspace snapshot")
from pricing.extractors import (
    UsageBreakdown,
    ResponseBreakdown,
    UsageExtractor,
    Extractor,
    get_extractor,
)
from pricing.aggregator import (
    RequestDetailsBuffer,
    RequestDetails,
    get_request_buffer,
    get_cost_aggregator,
    FLUSH_BATCH_SIZE,
    FLUSH_INTERVAL_SECONDS,
)
from pricing.interceptor import (
    CostInterceptor,
    wrap_custom_client,
)

# Compatibility aliases for the current simplified module surface.
CostExtractor = UsageExtractor
CostBreakdown = ResponseBreakdown
AnthropicExtractor = Extractor
OpenAIExtractor = Extractor
AnthropicInterceptor = CostInterceptor
OpenAIInterceptor = CostInterceptor


def wrap_anthropic_client(client, response_to_dict=None, interceptor=None, static_metadata=None):
    return wrap_custom_client(
        client=client,
        provider="anthropic",
        method_path="messages.create",
        response_to_dict=response_to_dict,
        interceptor=interceptor,
        static_metadata=static_metadata,
    )


def wrap_openai_client(client, response_to_dict=None, interceptor=None, static_metadata=None):
    return wrap_custom_client(
        client=client,
        provider="openai",
        method_path="chat.completions.create",
        response_to_dict=response_to_dict,
        interceptor=interceptor,
        static_metadata=static_metadata,
    )

__all__ = [
    # Manager
    "PricingManager",
    "BackendPricingOrchestrator",
    "get_pricing_manager",
    "get_backend_pricing_orchestrator",
    # Extractors
    "CostExtractor",
    "UsageBreakdown",
    "CostBreakdown",
    "ResponseBreakdown",
    "UsageExtractor",
    "Extractor",
    "AnthropicExtractor",
    "OpenAIExtractor",
    "get_extractor",
    # Buffer (replaces aggregator)
    "RequestDetailsBuffer",
    "RequestDetails",
    "get_request_buffer",
    "get_cost_aggregator",
    "FLUSH_BATCH_SIZE",
    "FLUSH_INTERVAL_SECONDS",
    # Interceptor
    "CostInterceptor",
    "AnthropicInterceptor",
    "OpenAIInterceptor",
    "wrap_anthropic_client",
    "wrap_openai_client",
    "wrap_custom_client",
]
