"""LLM Cost Observability SDK."""

from sdk import CostAnalyticsSDK, get_sdk
from pricing import (
    PricingManager,
    get_pricing_manager,
    CostExtractor,
    CostBreakdown,
    AnthropicExtractor,
    OpenAIExtractor,
    get_extractor,
    RequestDetailsBuffer,
    RequestDetails,
    get_request_buffer,
    get_cost_aggregator,
    CostInterceptor,
    AnthropicInterceptor,
    OpenAIInterceptor,
    wrap_anthropic_client,
    wrap_openai_client,
    wrap_custom_client,
    FLUSH_BATCH_SIZE,
    FLUSH_INTERVAL_SECONDS,
)

__version__ = "0.1.0"
__all__ = [
    # Main SDK
    "CostAnalyticsSDK",
    "get_sdk",
    # Pricing
    "PricingManager",
    "get_pricing_manager",
    # Extractors
    "CostExtractor",
    "CostBreakdown",
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
