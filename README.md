# LLM Cost Observability SDK

A production-ready, signal-plus-pull model SDK for **per-request cost analytics** across LLM providers (Anthropic, OpenAI, and extensible to others).

**Key Design Principle**: Client credentials never leave client infrastructure. SDK intercepts API responses, extracts usage, computes costs, and aggregates locally.

## Features

✅ **Multi-Provider Support**: Anthropic, OpenAI, extensible architecture  
✅ **Per-Request Cost Tracking**: Detailed cost breakdowns with token counts  
✅ **Cache-Aware Pricing**: Handles cache creation/read tokens per provider  
✅ **Automatic Pricing Sync**: Daily sync from LiteLLM upstream with smart fallback  
✅ **Zero Data Exfiltration**: All processing on client side  
✅ **Production Ready**: Aggregation, windowing, export, and alerting  
✅ **Easy Integration**: Wrap existing clients with one line  

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```python
from anthropic import Anthropic
from pricing import wrap_anthropic_client, get_cost_aggregator

# Create and wrap client
client = Anthropic()
client = wrap_anthropic_client(client)

# Use normally - costs tracked automatically
response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=100,
    messages=[{"role": "user", "content": "What is AI?"}],
)

# Get metrics
aggregator = get_cost_aggregator()
metrics = aggregator.get_aggregated_metrics()
print(f"Total cost: ${metrics.total_cost:.6f}")
print(f"Total requests: {metrics.total_requests}")
print(f"By model: {metrics.by_model}")
```

### OpenAI Example

```python
from openai import OpenAI
from pricing import wrap_openai_client, get_cost_aggregator

client = OpenAI()
client = wrap_openai_client(client)

response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello!"}],
)

metrics = get_cost_aggregator().get_aggregated_metrics()
print(f"Total cost: ${metrics.total_cost:.6f}")
```

## Architecture

### Signal-Plus-Pull Model

```
┌─────────────────────────────────────────────────────────────┐
│ Client Application (Your Code)                              │
├─────────────────────────────────────────────────────────────┤
│ + LLM Client (Anthropic/OpenAI)                             │
│   └─ Wrapped with CostInterceptor                           │
│      └─ Extracts usage from response (SIGNAL)               │
│         └─ Looks up pricing (PULL from local/sync)          │
│            └─ Computes cost + aggregates                    │
└─────────────────────────────────────────────────────────────┘
         ↓ (API call)
    LLM Provider API (no creds exposed)
         ↓ (response)
    Pricing Sync (daily, silent fallback)
         ↓
    Local pricing.json (bundled fallback)
```

### Core Components

1. **Pricing Manager** (`src/pricing/manager.py`)
   - Syncs from [LiteLLM upstream](https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json) daily
   - Hash-diff detection: only updates on changes
   - Silent fallback to bundled `pricing.json` on network failure
   - Tracks sync state and failures

2. **Cost Extractors** (`src/pricing/extractors.py`)
   - **Anthropic**: Extracts `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
   - **OpenAI**: Maps `prompt_tokens` → `input_tokens`, `completion_tokens` → `output_tokens`, `cached_prompt_tokens` → `cache_read_tokens`
   - Provider-specific cost formulas with cache pricing

3. **Cost Aggregator** (`src/pricing/aggregator.py`)
   - Records per-request: timestamp, model, provider, tokens, cost, metadata
   - Aggregates: total cost, by model, by provider, time windows
   - Exports to JSON for integration with billing systems

4. **Interceptor** (`src/pricing/interceptor.py`)
   - Non-invasive wrapper around client library calls
   - Routes to appropriate provider extractor
   - Records to aggregator
   - Provider-specific interceptors for easy wrapping

## Cost Extraction Details

### Anthropic `/v1/messages`

**Usage fields extracted**:
```python
{
    "input_tokens": int,
    "output_tokens": int,
    "cache_creation_input_tokens": int,  # Tokens cached for next request
    "cache_read_input_tokens": int,      # Cached tokens reused
}
```

**Cost formula**:
```
input_cost = (input_tokens * input_rate + cache_read_tokens * cache_read_rate) / 1_000_000
output_cost = output_tokens * output_rate / 1_000_000
cache_creation_cost = cache_creation_tokens * cache_creation_rate / 1_000_000
total_cost = input_cost + output_cost + cache_creation_cost
```

**Cache pricing** (per LiteLLM):
- `cache_read_rate` ≈ 10% of `input_rate` (90% discount on cached input)
- `cache_creation_rate` ≈ 125% of `input_rate` (25% premium for creating cache)

### OpenAI ChatCompletion

**Usage fields extracted**:
```python
{
    "input_tokens": prompt_tokens,
    "output_tokens": completion_tokens,
    "cache_read_tokens": cached_prompt_tokens,
}
```

**Cost formula**:
```
input_cost = (input_tokens * input_rate + cache_read_tokens * cache_read_rate) / 1_000_000
output_cost = output_tokens * output_rate / 1_000_000
total_cost = input_cost + output_cost
```

## Pricing Format

### Bundled Pricing File (`src/pricing/pricing.json`)

```json
{
  "claude-3-opus-20240229": {
    "input_cost_per_1m_tokens": 15.0,
    "output_cost_per_1m_tokens": 75.0,
    "cache_creation_cost_per_1m_tokens": 18.75,
    "cache_read_cost_per_1m_tokens": 1.5
  },
  "gpt-3.5-turbo": {
    "input_cost_per_1m_tokens": 0.50,
    "output_cost_per_1m_tokens": 1.50,
    "cache_read_cost_per_1m_tokens": 0.25
  }
}
```

### Upstream Sync Strategy

- **Primary source**: LiteLLM's `model_prices_and_context_window.json`
- **Sync interval**: Daily (configurable via `PRICING_SYNC_INTERVAL_HOURS`)
- **Change detection**: Hash-based (only update on content change)
- **Fallback**: Bundled `pricing.json` + logs warning
- **State tracking**: Stored in `pricing_sync.json`
- **Error handling**: Silent fallback on network errors, continues with local pricing

## Usage Examples

### Get Aggregated Metrics

```python
from pricing import get_cost_aggregator

agg = get_cost_aggregator()
metrics = agg.get_aggregated_metrics()

print(f"Total cost: ${metrics.total_cost:.6f}")
print(f"Total requests: {metrics.total_requests}")
print(f"By model: {metrics.by_model}")
print(f"By provider: {metrics.by_provider}")
print(f"Input tokens: {metrics.total_input_tokens}")
print(f"Output tokens: {metrics.total_output_tokens}")
print(f"Cache read tokens: {metrics.total_cache_read_tokens}")
print(f"Cache creation tokens: {metrics.total_cache_creation_tokens}")
```

### Time-Window Metrics

```python
# Last hour
metrics_1h = agg.get_metrics_in_window(minutes=60)

# Last 24 hours
metrics_24h = agg.get_metrics_in_window(minutes=1440)

print(f"Last hour: ${metrics_1h.total_cost:.6f}")
```

### Request-Level Details

```python
# Get all requests
all_requests = agg.get_requests_in_window(minutes=60)

for req in all_requests:
    print(f"{req.timestamp} | {req.model} | ${req.total_cost:.6f}")
```

### Export Costs

```python
# Export all recorded requests
agg.export_requests("costs.json")

# File contains list of:
# {
#   "timestamp": "2024-01-15T10:30:45.123456",
#   "request_id": "req_abc123",
#   "model": "claude-3-opus-20240229",
#   "provider": "anthropic",
#   "total_cost": 0.001234,
#   "input_tokens": 100,
#   "output_tokens": 50,
#   "cache_read_tokens": 0,
#   "cache_creation_tokens": 0,
#   "stop_reason": "end_turn",
#   "metadata": {}
# }
```

### Manual Cost Computation

```python
from pricing import AnthropicExtractor, get_pricing_manager

# Mock response from Anthropic API
response = {
    "model": "claude-3-opus-20240229",
    "usage": {
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    },
}

# Extract and compute
extractor = AnthropicExtractor()
usage = extractor.extract_usage(response)

pricing_mgr = get_pricing_manager()
pricing = pricing_mgr.get_pricing("claude-3-opus-20240229")

cost = extractor.compute_cost(usage, pricing)
print(f"Input cost: ${cost.input_cost:.6f}")
print(f"Output cost: ${cost.output_cost:.6f}")
print(f"Total cost: ${cost.total_cost:.6f}")
```

## Adding New LLM Providers

### Step 1: Create Provider Extractor

```python
# In src/pricing/extractors.py

class MyProviderExtractor(CostExtractor):
    """Extract costs from MyProvider API."""
    
    def extract_usage(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract usage fields from response."""
        try:
            usage_obj = response.get("usage_info", {})
            return {
                "input_tokens": usage_obj.get("prompt_tokens", 0),
                "output_tokens": usage_obj.get("response_tokens", 0),
                "cache_read_tokens": usage_obj.get("cached_tokens", 0),
                "cache_creation_tokens": 0,
            }
        except Exception as e:
            logger.error(f"Failed to extract usage: {e}")
            return None
    
    def extract_model(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract model from response."""
        return response.get("model_name")
    
    def compute_cost(self, usage: Dict[str, int], pricing: Dict[str, float]) -> CostBreakdown:
        """Compute cost using provider-specific formula."""
        breakdown = CostBreakdown(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_tokens", 0),
            provider="my-provider",
            raw_usage=usage,
        )
        
        input_rate = pricing.get("input_cost_per_1m_tokens", 0)
        output_rate = pricing.get("output_cost_per_1m_tokens", 0)
        
        breakdown.input_cost = (breakdown.input_tokens * input_rate) / 1_000_000
        breakdown.output_cost = (breakdown.output_tokens * output_rate) / 1_000_000
        breakdown.total_cost = breakdown.input_cost + breakdown.output_cost
        
        return breakdown
```

### Step 2: Register in Extractors Dict

```python
EXTRACTORS: Dict[str, type] = {
    "anthropic": AnthropicExtractor,
    "openai": OpenAIExtractor,
    "my-provider": MyProviderExtractor,  # Add here
}
```

### Step 3: Add Pricing to `pricing.json`

```json
{
  "my-model-v1": {
    "input_cost_per_1m_tokens": 1.0,
    "output_cost_per_1m_tokens": 2.0
  }
}
```

### Step 4: Create Optional Provider Interceptor

```python
class MyProviderInterceptor(CostInterceptor):
    """Wrapper for MyProvider client library."""
    
    def wrap_client(self, client: Any) -> Any:
        """Wrap client to intercept calls."""
        original_call = client.complete
        
        def wrapped(*args, **kwargs):
            response = original_call(*args, **kwargs)
            
            response_dict = (
                response.model_dump() if hasattr(response, 'model_dump')
                else response.__dict__
            )
            
            self.process_response(
                response_dict,
                provider='my-provider',
                metadata={'method': 'complete'},
            )
            
            return response
        
        client.complete = wrapped
        return client
```

## Configuration

### Environment Variables

```bash
# Pricing sync interval (hours)
export PRICING_SYNC_INTERVAL_HOURS=24

# Disable pricing sync
export DISABLE_PRICING_SYNC=false
```

### Programmatic Configuration

```python
from pricing import get_pricing_manager

manager = get_pricing_manager()

# Manual sync
manager.sync_from_upstream()

# Check sync state
print(manager.sync_state)
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=src tests/

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/unit/pricing/test_extractors.py -v

# Run with output
pytest -s tests/
```

## Production Deployment

### Best Practices

1. **Enable automatic pricing sync**:
   ```python
   sdk = CostAnalyticsSDK(auto_sync_pricing=True)
   ```

2. **Monitor for sync failures**:
   ```python
   manager = get_pricing_manager()
   if manager.sync_state.get("sync_failures", 0) > 5:
       logger.warning("Multiple pricing sync failures")
   ```

3. **Export metrics regularly**:
   ```python
   aggregator = get_cost_aggregator()
   aggregator.export_requests("daily_costs.json")
   ```

4. **Clear metrics periodically** (optional):
   ```python
   # Keep only last 7 days
   old_requests = [
       r for r in aggregator.requests
       if (datetime.utcnow() - r.timestamp).days > 7
   ]
   # Archive old_requests, then clear aggregator
   ```

5. **Set up alerts** for:
   - Single request costs exceeding threshold
   - Cost anomalies (unusual increase for model)
   - Pricing sync failures

### Integration with Billing Systems

```python
# Export costs
aggregator.export_requests("costs.json")

# Upload to your billing system
import json
with open("costs.json") as f:
    costs = json.load(f)

# Example: POST to your API
import requests
requests.post("https://billing.example.com/costs", json=costs)
```

## Phase 2: Cloud Infrastructure Billing

Future support for:
- **AWS**: Cost & Usage Report (CUR) + Athena querying
- **GCP**: BigQuery export integration
- **Azure**: Cost Management API

Same signal-plus-pull architecture: client pulls from cloud provider APIs, costs computed locally.

## Architecture Decisions

### Why Signal-Plus-Pull?

- **Security**: Credentials never leave client infrastructure
- **Privacy**: Cost data stays on client unless explicitly exported
- **Reliability**: Works offline, no external dependencies for core tracking
- **Scalability**: No central server bottleneck
- **Compliance**: Fits HIPAA, SOC2, and other compliance requirements

### Why LiteLLM for Pricing?

- **Comprehensive**: Covers 100+ LLM models
- **Current**: Updated regularly with new models
- **Open source**: Community-maintained, no vendor lock-in
- **Fallback**: Bundled pricing.json for offline operation

### Cost Formula Justification

Based on official provider documentation:
- **Anthropic**: Input/output costs per 1M tokens, cache rates documented
- **OpenAI**: Prices published per 1M tokens (prompt/completion)
- **Cache pricing**: Based on provider's published discounts

## Troubleshooting

### Pricing not updating

```python
from pricing import get_pricing_manager

manager = get_pricing_manager()

# Check sync state
print("Last sync:", manager.sync_state.get("last_sync"))
print("Sync failures:", manager.sync_state.get("sync_failures"))

# Force sync
success = manager.sync_from_upstream()
print("Sync success:", success)
```

### Missing pricing for model

```python
from pricing import get_pricing_manager

manager = get_pricing_manager()

# Check if model exists
pricing = manager.get_pricing("my-model")
print("Pricing found:", pricing is not None)

# List available models
print("Available models:", list(manager.pricing_data.keys())[:5])
```

### Costs seem wrong

1. Verify API response has `usage` field
2. Check pricing rates are correct for model
3. Manually compute: `(tokens * rate) / 1_000_000`
4. Compare with provider's dashboard

## License

MIT

## Support

For issues, questions, or contributions:
- GitHub: [cost_analytics-SDK](https://github.com/your-org/cost_analytics-SDK)
- Docs: See `docs/COST_ANALYTICS.md`
- Examples: See `examples/` directory
