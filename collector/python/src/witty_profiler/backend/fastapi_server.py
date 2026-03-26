"""FastAPI-based HTTP server implementation for Witty Profiler.

Provides full-featured REST API using FastAPI framework. Only registers
if fastapi and uvicorn dependencies are available.

Features:
    - RESTful endpoints for graph queries and control
    - Dynamic subscriber management
    - Auto-generated OpenAPI documentation
    - Async request handling
    - 404 redirect to help page

Dependencies:
    - fastapi>=0.115.0: Web framework
    - uvicorn>=0.34.0: ASGI server

Notes:
    Import failure silently skips registration - use fallback server instead.
"""

import json
import os
import time
from typing import Any

import yaml

from witty_profiler.backend.base import Server
from witty_profiler.backend.default_server import OnlineDisabledServer
from witty_profiler.common.constants import WittyProfilerServerConstants as ASC
from witty_profiler.common.env_manager import EnvManager
from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager
from witty_profiler.controller.witty_profiler_core import WittyProfilerCore
from witty_profiler.graph.graph import Graph
from witty_profiler.subscriber.subscriber_base import (
    create_subscriber,
    get_available_subscriber_types,
)

LOGGER = get_logger(__name__)


if not EnvManager().fastapi_available():
    LOGGER.debug("FastAPI dependencies not available, skipping FastAPI server")
else:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

    class FastAPIServer(OnlineDisabledServer):
        """FastAPI-based server providing full REST API.

        Wraps WittyProfilerCore with HTTP endpoints for querying topology graphs,
        controlling collection, and managing subscribers.

        Attributes:
            _app: FastAPI application instance (lazy init)

        Routes:
            GET /: API documentation
            GET /help: Plain text help
            GET /graph: Latest topology graph
            GET /compressed_graph: Graph string summary
            GET /status: Collection status
            POST /control/start: Start collection
            POST /control/stop: Stop collection
            POST /control/trigger: Manual collection
            POST /subscriber: Register subscriber
            DELETE /subscriber/{name}: Unregister subscriber
            GET /subscribers: List subscribers
        """

        def __init__(self, core: WittyProfilerCore):
            super().__init__(core)
            self._app = None  # Lazy initialization
            self._env_manager: EnvManager = EnvManager.get_instance()

        def run_online(self, addr: str, port: int):
            """Start HTTP server and begin topology collection.

            Blocks until shutdown (Ctrl+C or SIGTERM).

            Args:
                addr: Server bind address
                port: Server bind port
            """
            if self._app is None:
                self._app = self._create_app()

            # Start collection before serving
            self._core.start()
            LOGGER.info(f"Starting Witty Profiler server at {addr}:{port}")

            try:
                uvicorn.run(self._app, host=addr, port=port, log_level="info")
            except KeyboardInterrupt:
                LOGGER.info("Shutting down Witty Profiler server...")
            finally:
                self._core.stop()

        def _create_app(self) -> Any:
            """Create and configure FastAPI application with all endpoints."""
            app = self._build_base_app()

            # Collect endpoint summaries as routes are registered
            endpoint_summaries: list[str] = []

            self._register_root_routes(app, endpoint_summaries)
            self._register_graph_routes(app, endpoint_summaries)
            self._register_status_routes(app, endpoint_summaries)
            self._register_control_routes(app, endpoint_summaries)
            self._register_subscriber_routes(app, endpoint_summaries)
            self._register_help_routes(app, endpoint_summaries)
            self._register_not_found_handler(app)
            return app

        def _build_base_app(self):
            """Create FastAPI app with metadata."""
            return FastAPI(
                title=ASC.API_TITLE,
                description=ASC.API_DESCRIPTION,
                version=ASC.API_VERSION,
            )

        def _register_root_routes(self, app, endpoints: list[str]):
            """Register root endpoint with API documentation."""

            @app.get(ASC.ROUTE_ROOT)
            async def root():
                return self._get_json_response(
                    {
                        "service": ASC.API_TITLE,
                        "version": ASC.API_VERSION,
                        "endpoints": {
                            f"GET {ASC.ROUTE_ROOT}": "This documentation",
                            f"GET {ASC.ROUTE_GRAPH}": "Retrieve latest topology graph",
                            f"GET {ASC.ROUTE_COMPRESSED_GRAPH}": "Retrieve graph summary string",
                            f"GET {ASC.ROUTE_STATUS}": "Collection status and statistics",
                            f"POST {ASC.ROUTE_CONTROL_START}": "Start topology collection",
                            f"POST {ASC.ROUTE_CONTROL_STOP}": "Stop topology collection",
                            f"POST {ASC.ROUTE_CONTROL_TRIGGER}": "Manually trigger collection",
                            f"POST {ASC.ROUTE_CONTROL_CLEAR}": "Clear collected data",
                            f"POST {ASC.ROUTE_SUBSCRIBER}": "Register new subscriber",
                            f"DELETE {ASC.ROUTE_SUBSCRIBER_NAME}": "Unregister subscriber",
                            f"GET {ASC.ROUTE_SUBSCRIBERS}": "List all subscribers",
                        },
                    }
                )

            endpoints.append(f"GET {ASC.ROUTE_ROOT} - API documentation")

        def _register_help_routes(self, app, endpoints: list[str]):
            """Register /help endpoint with plain text usage."""
            help_text = self._build_help_text(endpoints)

            @app.get(ASC.ROUTE_HELP)
            async def help_route():
                return PlainTextResponse(help_text)

        def _register_not_found_handler(self, app):
            """Register 404 handler redirecting to /help."""

            @app.exception_handler(404)
            async def not_found_handler(request, exc):
                return RedirectResponse(url=ASC.ROUTE_HELP, status_code=307)

        def _build_help_text(self, endpoints: list[str]) -> str:
            """Build help text from endpoint summaries."""
            return ASC.HELP_HEADER + "\n".join(endpoints)

        def _register_graph_routes(self, app, endpoints: list[str]):
            """Register /graph endpoint."""

            @app.get(ASC.ROUTE_GRAPH)
            async def get_graph():
                graph: Graph = self._core.get_last_graph()
                return self._get_json_response(graph.model_dump())

            @app.get(ASC.ROUTE_COMPRESSED_GRAPH)
            async def get_compressed_graph():
                graph: Graph = self._core.get_last_graph()
                return PlainTextResponse(str(graph))

            endpoints.append(f"GET {ASC.ROUTE_GRAPH} - Retrieve latest topology graph")
            endpoints.append(
                f"GET {ASC.ROUTE_COMPRESSED_GRAPH} - Retrieve graph summary string"
            )

        def _register_status_routes(self, app, endpoints: list[str]):
            """Register /status endpoint."""

            @app.get(ASC.ROUTE_STATUS)
            async def get_status():
                graph = self._core.get_last_graph()
                collector_set = self._core.get_collector_set()
                sub_collection = self._core.subscriber_collection()
                collectors = getattr(collector_set, "subcollectors", [])

                return self._get_json_response(
                    {
                        "running": self._core.is_running(),
                        "graph": {
                            "node_count": len(graph.nodes),
                            "edge_count": len(graph.edges),
                        },
                        "collectors": {
                            "count": len(collectors),
                            "types": [
                                collector.__class__.__name__ for collector in collectors
                            ],
                        },
                        "subscribers": {
                            "count": len(sub_collection.subscribers),
                            "names": list(sub_collection.subscribers.keys()),
                        },
                    }
                )

            endpoints.append(
                f"GET {ASC.ROUTE_STATUS} - Collection status and statistics"
            )

        def _register_control_routes(self, app, endpoints: list[str]):
            """Register collection control endpoints."""

            @app.post(ASC.ROUTE_CONTROL_START)
            async def start_collection():
                try:
                    self._core.start()
                    return self._get_json_response(
                        {"status": "success", "message": "Collection started"}
                    )
                except Exception as exc:
                    LOGGER.error("Failed to start collection: %s", exc)
                    raise HTTPException(status_code=500, detail=str(exc))

            @app.post(ASC.ROUTE_CONTROL_STOP)
            async def stop_collection():
                try:
                    self._core.stop()
                    return self._get_json_response(
                        {"status": "success", "message": "Collection stopped"}
                    )
                except Exception as exc:
                    LOGGER.error("Failed to stop collection: %s", exc)
                    raise HTTPException(status_code=500, detail=str(exc))

            @app.post(ASC.ROUTE_CONTROL_TRIGGER)
            async def trigger_collection():
                try:
                    self._core.trigger_collect()
                    graph = self._core.get_last_graph()
                    return self._get_json_response(
                        {
                            "status": "success",
                            "message": "Collection triggered",
                            "graph_summary": graph.describe(),
                        }
                    )
                except Exception as exc:
                    LOGGER.error("Failed to trigger collection: %s", exc)
                    raise HTTPException(status_code=500, detail=str(exc))

            @app.post(ASC.ROUTE_CONTROL_CLEAR)
            async def clear_collection():
                try:
                    self._core.trigger_clear()
                    return self._get_json_response(
                        {
                            "status": "success",
                            "message": "Collected data cleared",
                        }
                    )
                except Exception as exc:
                    LOGGER.error("Failed to clear collection: %s", exc)
                    raise HTTPException(status_code=500, detail=str(exc))

            endpoints.extend(
                [
                    f"POST {ASC.ROUTE_CONTROL_START} - Start topology collection",
                    f"POST {ASC.ROUTE_CONTROL_STOP} - Stop topology collection",
                    f"POST {ASC.ROUTE_CONTROL_TRIGGER} - Manually trigger collection",
                    f"POST {ASC.ROUTE_CONTROL_CLEAR} - Clear collected data",
                ]
            )

        def _register_subscriber_routes(self, app, endpoints: list[str]):
            """Register subscriber management endpoints."""

            @app.post(ASC.ROUTE_SUBSCRIBER)
            async def register_subscriber(request: Request):
                try:
                    config = await request.json()
                    subscriber = create_subscriber(config)
                    if subscriber is None:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Failed to create subscriber. Available types: "
                                f"{get_available_subscriber_types()}"
                            ),
                        )

                    sub_collection = self._core.subscriber_collection()
                    sub_collection.register(
                        subscriber.name, subscriber, enable_override=True
                    )

                    return self._get_json_response(
                        {
                            "status": "success",
                            "message": f"Subscriber '{subscriber.name}' registered",
                            "subscriber_name": subscriber.name,
                        }
                    )
                except HTTPException:
                    raise
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
                except Exception as exc:
                    LOGGER.error("Failed to register subscriber: %s", exc)
                    raise HTTPException(status_code=500, detail=str(exc))

            @app.delete(ASC.ROUTE_SUBSCRIBER_NAME)
            async def unregister_subscriber(name: str):
                try:
                    sub_collection = self._core.subscriber_collection()
                    if name not in sub_collection.subscribers:
                        raise HTTPException(
                            status_code=404, detail=f"Subscriber '{name}' not found"
                        )

                    sub_collection.unregister_subscriber(name)
                    return self._get_json_response(
                        {
                            "status": "success",
                            "message": f"Subscriber '{name}' unregistered",
                        }
                    )
                except HTTPException:
                    raise
                except Exception as exc:
                    LOGGER.error("Failed to unregister subscriber: %s", exc)
                    raise HTTPException(status_code=500, detail=str(exc))

            @app.get(ASC.ROUTE_SUBSCRIBERS)
            async def list_subscribers():
                sub_collection = self._core.subscriber_collection()
                subscribers_info = [
                    {
                        "name": name,
                        "type": sub.subscriber_type,
                        "expected_update_interval": sub.expected_update_interval,
                    }
                    for name, sub in sub_collection.subscribers.items()
                ]
                return self._get_json_response(
                    {
                        "count": len(subscribers_info),
                        "subscribers": subscribers_info,
                        "available_types": get_available_subscriber_types(),
                    }
                )

            endpoints.extend(
                [
                    f"POST {ASC.ROUTE_SUBSCRIBER} - Register new subscriber",
                    f"DELETE {ASC.ROUTE_SUBSCRIBER_NAME} - Unregister subscriber",
                    f"GET {ASC.ROUTE_SUBSCRIBERS} - List all subscribers",
                ]
            )

        def _get_json_response(self, content: dict) -> JSONResponse:
            """Return the response model used by this server."""

            response = JSONResponse(
                content={
                    "env": self._env_manager.get_env_dict(),
                    "content": content,
                }
            )

            return response
