"""Telemetry client for flushing usage metrics to the centralized server."""

import logging
import uuid
import requests
from typing import List, Optional

from pricing.aggregator import RequestDetails

logger = logging.getLogger(__name__)

class TelemetryClient:
    """HTTP client to send batched request metadata to the server."""

    def __init__(
        self,
        server_url: str,
        endpoint: str = "/v1/telemetry/flush",
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.server_url = server_url.rstrip("/")
        self.endpoint = endpoint.lstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.client_id = str(uuid.uuid4())

    def flush_batch(self, batch: List[RequestDetails]) -> None:
        """
        Callback bound to the RequestDetailsBuffer on_flush.
        Sends the batched extraction details to the server.
        """
        if not batch:
            return

        url = f"{self.server_url}/{self.endpoint}"
        
        headers = {
            "Content-Type": "application/json",
            "X-Client-ID": self.client_id,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "client_id": self.client_id,
            "batch": [req.to_dict() for req in batch]
        }

        try:
            logger.debug(f"Flushing batch of {len(batch)} to {url}")
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            logger.info(f"Successfully flushed {len(batch)} requests to server.")
        except requests.RequestException as e:
            logger.error(f"Failed to flush telemetry batch: {e}")
            raise
