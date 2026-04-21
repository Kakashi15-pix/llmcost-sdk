"""
Pricing configuration and management for LLM providers.
Implements signal-plus-pull model with primary upstream sync and local fallback.
"""
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path
import requests
import logging

logger = logging.getLogger(__name__)

# Upstream pricing source
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
PRICING_SYNC_INTERVAL_HOURS = 24
PRICING_CACHE_PATH = Path(__file__).parent / "pricing_cache.json"
PRICING_SYNC_STATE_PATH = Path(__file__).parent / "pricing_sync.json"


class PricingManager:
    """Manages pricing data with upstream sync and local fallback."""

    def __init__(self):
        self.pricing_data: Dict[str, Dict[str, Any]] = {}
        self.sync_state = self._load_sync_state()
        self._load_pricing()

    def _load_sync_state(self) -> Dict[str, Any]:
       
        if PRICING_SYNC_STATE_PATH.exists():
            try:
                with open(PRICING_SYNC_STATE_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load sync state: {e}")
        return {"last_sync": None, "last_hash": None, "sync_failures": 0}

    def _save_sync_state(self) -> None:
        """Save sync state tracking."""
        try:
            with open(PRICING_SYNC_STATE_PATH, "w") as f:
                json.dump(self.sync_state, f)
        except Exception as e:
            logger.warning(f"Failed to save sync state: {e}")

    def _should_sync(self) -> bool:
        """Check if sync should occur based on interval."""
        last_sync = self.sync_state.get("last_sync")
        if not last_sync:
            return True
        
        last_sync_dt = datetime.fromisoformat(last_sync)
        return datetime.utcnow() - last_sync_dt > timedelta(hours=PRICING_SYNC_INTERVAL_HOURS)

    def _get_hash(self, data: Dict[str, Any]) -> str:
        """Compute hash of pricing data for change detection."""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def sync_from_upstream(self) -> bool:
        """
        Sync pricing from LiteLLM upstream.
        Returns True if successful, False otherwise (fallback to local).
        """
        if not self._should_sync():
            logger.debug("Pricing sync interval not reached")
            return True

        try:
            logger.debug(f"Syncing pricing from {LITELLM_PRICING_URL}")
            response = requests.get(LITELLM_PRICING_URL, timeout=10)
            response.raise_for_status()
            
            upstream_data = response.json()
            current_hash = self._get_hash(upstream_data)
            
            # Only update if content changed
            if current_hash != self.sync_state.get("last_hash"):
                self.pricing_data = upstream_data
                self.sync_state.update({
                    "last_sync": datetime.utcnow().isoformat(),
                    "last_hash": current_hash,
                    "sync_failures": 0
                })
                self._save_sync_state()
                logger.info("Pricing data synced successfully")
                return True
            else:
                logger.debug("Pricing data unchanged from upstream")
                self.sync_state["last_sync"] = datetime.utcnow().isoformat()
                self._save_sync_state()
                return True
                
        except Exception as e:
            logger.warning(f"Failed to sync pricing: {e}")
            self.sync_state["sync_failures"] = self.sync_state.get("sync_failures", 0) + 1
            self._save_sync_state()
            return False

    def _load_pricing(self) -> None:
        """Load pricing from cache or bundled file."""
        # Try cache first
        if PRICING_CACHE_PATH.exists():
            try:
                with open(PRICING_CACHE_PATH) as f:
                    self.pricing_data = json.load(f)
                logger.debug("Loaded pricing from cache")
                return
            except Exception as e:
                logger.debug(f"Failed to load pricing cache: {e}")

        # Fallback to bundled pricing
        bundled_path = Path(__file__).parent / "pricing.json"
        if bundled_path.exists():
            try:
                with open(bundled_path) as f:
                    self.pricing_data = json.load(f)
                logger.debug("Loaded pricing from bundled file")
                return
            except Exception as e:
                logger.error(f"Failed to load bundled pricing: {e}")

        logger.warning("No pricing data available")
        self.pricing_data = {}

    def _save_cache(self) -> None:
        """Save pricing data to cache."""
        try:
            with open(PRICING_CACHE_PATH, "w") as f:
                json.dump(self.pricing_data, f)
        except Exception as e:
            logger.warning(f"Failed to save pricing cache: {e}")

    def get_pricing(self, model: str, provider: str = None) -> Optional[Dict[str, Any]]:
        """
        Get pricing for a model.
        
        Args:
            model: Model identifier (e.g., 'claude-3-opus-20240229')
            provider: Optional provider name (inferred from model if not provided)
        
        Returns:
            Pricing dict with input_cost_per_1m_tokens, output_cost_per_1m_tokens, etc.
            None if model not found.
        """
        if not self.pricing_data:
            return None

        # Try exact match first
        if model in self.pricing_data:
            return self.pricing_data[model]

        # If provider given, try provider-prefixed lookup
        if provider:
            provider_model = f"{provider}/{model}"
            if provider_model in self.pricing_data:
                return self.pricing_data[provider_model]

        logger.warning(f"Pricing not found for model: {model}")
        return None

    def update_from_response(self, data: Dict[str, Any]) -> None:
        """Update pricing cache from upstream data."""
        if data:
            self.pricing_data = data
            self._save_cache()


# Global pricing manager instance
_pricing_manager = None


def get_pricing_manager() -> PricingManager:
    """Get or create global pricing manager."""
    global _pricing_manager
    if _pricing_manager is None:
        _pricing_manager = PricingManager()
    return _pricing_manager
