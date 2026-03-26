"""Command-line interface for Anansi topology collection server.

Provides a simple CLI to start Anansi in online (server) or offline (batch) mode.

Usage:
    # Start HTTP server with config defaults
    python -m anansi

    # Start server with custom address/port (overrides config)
    python -m anansi --host 0.0.0.0 --port 9090

    # Load specific config file
    python -m anansi --config path/to/config.json

    # Run offline for 30 seconds and output graph JSON
    python -m anansi --offline --duration 30

    # Show help
    python -m anansi --help

Configuration:
    Settings loaded from GlobalConfigManager (default or --config file).
    CLI arguments override configuration values.

Examples:
    # Production server using config.json
    python -m anansi --config configs/production.json

    # Development server on localhost (override config)
    python -m anansi --host 127.0.0.1 --port 18090

    # Quick offline test
    python -m anansi --offline --duration 10

Notes:
    Server mode (default) requires fastapi and uvicorn installed.
    Install with: uv sync --group server
    or: pip install anansi[server]
    CLI enforces a single running instance via a process lock file.
"""

import argparse
import json
import sys

from anansi.collector.local_collector.static_collector import StaticCollector
from anansi.common.constants import AnansiProcessConstants
from anansi.common.logging import get_logger
from anansi.common.process_lock import ProcessFileLock
from anansi.config_manager.config_manager import GlobalConfigManager
from anansi.tools.build import DepBuilder

LOGGER = get_logger(__name__)


def main():
    """Parse command-line arguments and start Anansi server."""
    parser = argparse.ArgumentParser(
        prog="anansi",
        description="Anansi - Automated topology detection for AI systems",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start HTTP server with config defaults
  python -m anansi
  
  # Load specific config file
  python -m anansi --config configs/production.json
  
  # Override config with CLI args
  python -m anansi --host 0.0.0.0 --port 9090
  
  # Offline batch mode
  python -m anansi --offline --duration 30
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration JSON file (optional)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify dependencies",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Server bind address (overrides config)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Server bind port (overrides config)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline mode (no HTTP server, fixed duration)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=10.0,
        help="Duration for offline mode in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        help="Logging level (e.g., VERBOSE, DEBUG, INFO, REPORT, WARNING, ERROR, CRITICAL)",
    )
    parser.add_argument(
        "--dump-config",
        "--dump",
        type=str,
        help="Path to output the whole configuration as JSON",
    )
    parser.add_argument(
        "--view-graph",
        action="store_true",
        help="Compress graph and view a graph",
    )
    parser.add_argument(
        "--pid",
        type=int,
        help="Target process ID to monitor (optional, overrides config start_nodes)",
    )

    args = parser.parse_args()

    try:
        # Load configuration
        if args.config:
            LOGGER.info(f"Loading configuration from {args.config}")
            # initailize the config manager with the config file
            GlobalConfigManager(args.config)

        if args.log_level:
            LOGGER.info(f"Setting log level to {args.log_level}")
            root_logger = get_logger(name="anansi", level=args.log_level)
            root_logger.setLevel(args.log_level)

        if args.dump_config:
            LOGGER.info(f"Dumping configuration to {args.dump_config}")
            GlobalConfigManager().dump_config(args.dump_config)
            return
        if args.view_graph:
            LOGGER.info("Compressing graph and viewing...")
            from anansi.tools.view import GraphViewTool

            graph_file = (
                input("Enter the path to the graph JSON file[topology.json]: ").strip()
                or "topology.json"
            )
            output_file = (
                input("Enter the output text file[blank for stdout]: ").strip() or None
            )

            GraphViewTool().view_graph_from_file(graph_file, output_file)
            return

        if args.verify:
            LOGGER.info("Verifying dependencies...")
            DepBuilder().verify_binaries()
            return

        if args.pid:
            LOGGER.info(f"Adding process with PID {args.pid} as seed node")
            StaticCollector().add_process_as_seed(args.pid)

        process_lock = ProcessFileLock(
            AnansiProcessConstants.LOCK_FILE(), lock_name="Anansi"
        )
        try:
            process_lock.acquire()
            LOGGER.info("Starting Anansi Server...")
        except RuntimeError as e:
            LOGGER.error(e)
            sys.exit(1)

        from anansi.backend.anansi import AnansiServer

        server: AnansiServer = AnansiServer.get_instance()

        if args.offline:
            process_lock.update_metadata(
                {
                    "mode": "offline",
                    "duration": args.duration,
                }
            )
            LOGGER.info(f"Starting Anansi in offline mode for {args.duration}s")
            server.run_offline(duration=args.duration)
            LOGGER.info("Anansi offline run complete")
        else:
            # CLI args override config
            config_mgr = GlobalConfigManager.get_instance()
            server_config = config_mgr.get_config().server_config
            host = args.host or server_config.server_addr.host
            port = args.port or server_config.server_addr.port

            if args.host or args.port:
                LOGGER.info("Using CLI arguments to override config")

            LOGGER.info("Press Ctrl+C to stop the server")
            process_lock.update_metadata(
                {
                    "mode": "online",
                    "host": host,
                    "port": port,
                }
            )
            server.run_online(addr=host, port=port)

    except KeyboardInterrupt:
        LOGGER.info("Received interrupt signal, shutting down...")
        sys.exit(0)
    except Exception as e:
        LOGGER.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
