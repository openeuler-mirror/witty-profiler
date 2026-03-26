"""RESTful backend client for Witty Profiler remote server communication.

Provides RestfulRemoteBackendClient, an HTTP client implementation that
communicates with Witty Profiler FastAPI servers using REST endpoints. Exposes
control operations, graph retrieval, and subscriber management.

Key Components:
    - RestfulRemoteBackendClient: Concrete HTTP client using urllib
    - Implements all RemoteBackendClient abstract methods
    - Routes sourced from WittyProfilerServerConstants for consistency

Features:
    - Control operations: start/stop/trigger/clear collection
    - Graph retrieval with env/content envelope parsing
    - Compressed graph retrieval via plain-text endpoint
    - Status and subscriber management endpoints
    - JSON request/response handling with stdlib urllib
    - Configurable timeout (default: 5.0s)

HTTP Protocol:
    - Uses Python stdlib urllib for HTTP requests (no external dependencies)
    - Content-Type: application/json for POST requests
    - Expects FastAPI server responses with env/content envelope
    - Empty response body returns {} instead of error

Error Handling:
    Raises RemoteBackendClientError on:
    - Network errors (connection refused, timeout)
    - HTTP errors (4xx, 5xx status codes)
    - JSON decoding failures
    - URLError from urllib

Usage:
    ```python
    client = RestfulRemoteBackendClient(
        server_addr=ServerAddr(host=\"192.168.1.100\", port=18090)
    )
    client.start_collection()
    graph_dict = client.fetch_graph()  # Returns {\"env\": ..., \"content\": ...}
    client.stop_collection()
    ```

Notes:
    - Routes from WittyProfilerServerConstants avoid path drift with server
    - Chinese notes preserved: 网络错误将抛出 RemoteBackendClientError，调用方需捕获处理
    - 返回值遵循服务端的约定（可能包含 env/content 包装）
"""

import json
from typing import Optional
from urllib import error, request

from witty_profiler.backend.backend_client.remote_backend import (
    RemoteBackendClient,
    RemoteBackendClientError,
)
from witty_profiler.common.constants import WittyProfilerServerConstants as ASC


class RestfulRemoteBackendClient(RemoteBackendClient):
    """HTTP client that talks to FastAPI backend via REST endpoints."""

    def start_collection(self):
        self._post(ASC.ROUTE_CONTROL_START)

    def stop_collection(self):
        self._post(ASC.ROUTE_CONTROL_STOP)

    def clear_collection(self):
        self._post(ASC.ROUTE_CONTROL_CLEAR)

    def trigger_collection(self):
        self._post(ASC.ROUTE_CONTROL_TRIGGER)

    def fetch_graph(self) -> dict:
        return self._request_json(ASC.ROUTE_GRAPH, method="GET")

    def fetch_compressed_graph(self) -> str:
        """Fetch the compressed graph string from the server."""
        return self._request_text(ASC.ROUTE_COMPRESSED_GRAPH, method="GET")

    # ---- Additional convenience endpoints ----
    def get_root(self) -> dict:
        """Fetch API root (documentation/help)."""
        return self._request_json(ASC.ROUTE_ROOT, method="GET")

    def get_status(self) -> dict:
        """Fetch current collection status from server."""
        return self._request_json(ASC.ROUTE_STATUS, method="GET")

    def register_subscriber(self, config: dict) -> dict:
        """Register a subscriber via POST payload."""
        return self._post(ASC.ROUTE_SUBSCRIBER, payload=config)

    def unregister_subscriber(self, name: str) -> dict:
        """Unregister a subscriber by name via DELETE."""
        path = ASC.ROUTE_SUBSCRIBER_NAME.replace("{name}", name)
        return self._request_json(path, method="DELETE")

    def list_subscribers(self) -> dict:
        """List all registered subscribers."""
        return self._request_json(ASC.ROUTE_SUBSCRIBERS, method="GET")

    def _post(self, path: str, payload: Optional[dict] = None) -> dict:
        return self._request_json(path, method="POST", payload=payload)

    def _request_json(
        self, path: str, method: str = "GET", payload: Optional[dict] = None
    ) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"}
        req = request.Request(url=url, data=data, headers=headers, method=method)

        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                text = resp.read().decode(charset)
                return json.loads(text) if text else {}
        except error.HTTPError as exc:  # pragma: no cover - defensive path
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RemoteBackendClientError(
                f"HTTP {exc.code} for {method} {path}: {detail}"
            ) from exc
        except error.URLError as exc:  # pragma: no cover - defensive path
            raise RemoteBackendClientError(
                f"Failed to reach {url}: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive path
            raise RemoteBackendClientError(
                f"Invalid JSON from {url}: {exc}".rstrip()
            ) from exc

    def _request_text(self, path: str, method: str = "GET") -> str:
        url = f"{self.base_url}{path}"
        req = request.Request(url=url, headers={}, method=method)

        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset)
        except error.HTTPError as exc:  # pragma: no cover - defensive path
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RemoteBackendClientError(
                f"HTTP {exc.code} for {method} {path}: {detail}"
            ) from exc
        except error.URLError as exc:  # pragma: no cover - defensive path
            raise RemoteBackendClientError(
                f"Failed to reach {url}: {exc.reason}"
            ) from exc
