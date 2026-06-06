"""Telemetry client for flushing usage metrics to the centralized server."""

from collections import deque
import logging
import threading
import uuid
from typing import Deque, List, Optional

import requests

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
        self._failed_batches: Deque[List[RequestDetails]] = deque(maxlen=5)
        self._lock = threading.Lock()

    def _snapshot_failed_batches(self) -> List[List[RequestDetails]]:
        """Capture previously failed batches without clearing them."""

        with self._lock:
            return [list(batch) for batch in self._failed_batches]

    def _clear_failed_batches(self) -> None:
        """Remove all retained failed flushes after a successful send."""

        with self._lock:
            self._failed_batches.clear()

    def _store_failed_batch(self, batch: List[RequestDetails]) -> None:
        """Keep at most the last five failed flushes for the next retry window."""

        if not batch:
            return

        with self._lock:
            self._failed_batches.append(list(batch))

    @staticmethod
    def _is_not_received_error(exc: requests.RequestException) -> bool:
        """Detect send failures where the server never returned a usable status code."""

        response = getattr(exc, "response", None)
        if response is None:
            return True

        status_code = getattr(response, "status_code", None)
        return status_code is None

    def _send_batch(self, batch: List[RequestDetails]) -> None:
        """Send one batch and raise on any non-success response."""

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
            "batch": [req.to_dict() for req in batch],
        }

        logger.debug(f"Flushing batch of {len(batch)} to {url}")
        response = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        logger.info(f"Successfully flushed {len(batch)} requests to server.")

    def _send_batch_with_retry(self, batch: List[RequestDetails]) -> bool:
        """Send a batch, retrying once immediately for 'not received' style failures."""

        try:
            self._send_batch(batch)
            return True
        except requests.RequestException as exc:
            if not self._is_not_received_error(exc):
                logger.error(f"Failed to flush telemetry batch: {exc}")
                return False

            logger.warning("Telemetry flush was not received, retrying once immediately")
            try:
                self._send_batch(batch)
                return True
            except requests.RequestException as retry_exc:
                logger.error(f"Telemetry flush failed after immediate retry: {retry_exc}")
                return False

    def flush_batch(self, batch: List[RequestDetails]) -> None:
        """
        Callback bound to the RequestDetailsBuffer on_flush.
        Sends the batched extraction details to the server.
        """
        if not batch:
            return

        pending_batches = self._snapshot_failed_batches()
        merged_batch: List[RequestDetails] = [request for failed_batch in pending_batches for request in failed_batch]
        merged_batch.extend(batch)

        if self._send_batch_with_retry(merged_batch):
            self._clear_failed_batches()
            return

        self._store_failed_batch(batch)
        logger.error(
            f"Stored failed telemetry flush for later retry; pending_failed_flushes={len(self._failed_batches)}"
        )

    def close(self) -> None:
        """Close the underlying HTTP session."""

        self.session.close()
