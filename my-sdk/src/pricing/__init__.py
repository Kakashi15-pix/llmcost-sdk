"""Cost analytics and pricing module."""

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

CostExtractor = UsageExtractor
CostBreakdown = ResponseBreakdown

__all__ = [
    # Extractors
    "CostExtractor",
    "UsageBreakdown",
    "CostBreakdown",
    "ResponseBreakdown",
    "UsageExtractor",
    "Extractor",
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
    "wrap_custom_client",
]
