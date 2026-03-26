"""Interactive Witty Profiler API client using `RestfulRemoteBackendClient`.

Provides an `ExampleClient` class with a `run()` loop that presents
numbered operations for interacting with the Witty Profiler server. Host and
port are provided via command-line arguments using `argparse`.

Detailed description:
        - Operations include: show API docs, status, start/stop/trigger/clear
            collection, get graph, get compressed graph, list/register/unregister
            subscribers.
    - Uses `RestfulRemoteBackendClient` for all requests to avoid direct
      third-party HTTP dependencies.

注意事项：
    - 需确保服务器先启动：`witty-profiler` 或 `python -m witty_profiler`。
    - 网络/JSON错误会显示友好提示，不会导致程序崩溃。
"""

import argparse
import json
import os
import time
from typing import Any, Dict

from witty_profiler.backend.backend_client.remote_restful_backend import (
    RestfulRemoteBackendClient,
)
from witty_profiler.config_manager.configs import ServerAddr


class ExampleClient:
    """Interactive client for Witty Profiler HTTP API.

    Args:
        host: Server hostname or IP
        port: Server port
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.client = RestfulRemoteBackendClient(ServerAddr(host=host, port=port))

    @staticmethod
    def pretty_print(title: str, data: Any):
        print(f"\n{'='*60}")
        print(f"  {title}")
        print("=" * 60)
        print(json.dumps(data, indent=2))

    def _show_menu(self):
        print("\nWitty Profiler API Client Menu")
        print("=" * 30)
        print(" 1) Show API documentation (/)")
        print(" 2) Show status (/status)")
        print(" 3) Start collection (/control/start)")
        print(" 4) Stop collection (/control/stop)")
        print(" 5) Trigger collection (/control/trigger)")
        print(" 6) Clear collection (/control/clear)")
        print(" 7) Get graph (/graph)")
        print(" 8) Get compressed graph (/compressed_graph)")
        print(" 9) List subscribers (/subscribers)")
        print("10) Register subscriber (/subscriber)")
        print("11) Unregister subscriber (/subscriber/{name})")
        print(" 0) Exit")

    def run(self):
        print("Witty Profiler API Client (interactive)")
        print("=" * 60)
        print(f"Connecting to: http://{self.host}:{self.port}")

        while True:
            self._show_menu()
            choice = input("Select an option: ").strip()
            try:
                if choice == "1":
                    self.pretty_print("API Documentation", self.client.get_root())
                elif choice == "2":
                    self.pretty_print("Current Status", self.client.get_status())
                elif choice == "3":
                    self.pretty_print("Start Result", self.client.start_collection())
                elif choice == "4":
                    self.pretty_print("Stop Result", self.client.stop_collection())
                elif choice == "5":
                    self.pretty_print(
                        "Trigger Result", self.client.trigger_collection()
                    )
                elif choice == "6":
                    self.pretty_print("Clear Result", self.client.clear_collection())
                elif choice == "7":
                    data = self.client.fetch_graph()
                    graph: dict = data.get("content", {})

                    self.pretty_print(
                        title=f"Topology Graph ({len(graph.get('nodes', []))} nodes, "
                        f"{len(graph.get('edges', []))} edges)",
                        data=data,
                    )
                    graph = data
                    dump_path = (
                        input("Dump path [local/topology.json]: ").strip()
                        or "local/topology.json"
                    )
                    os.makedirs(os.path.dirname(dump_path), exist_ok=True)
                    with open(dump_path, "wt") as f:
                        f.write(json.dumps(graph, indent=2))
                elif choice == "8":
                    compressed = self.client.fetch_compressed_graph()
                    print("\n" + compressed)
                elif choice == "9":
                    self.pretty_print("Subscribers", self.client.list_subscribers())
                elif choice == "10":
                    name = (
                        input("Subscriber name [example_subscriber]: ").strip()
                        or "example_subscriber"
                    )
                    sub_type = (
                        input(
                            "Subscriber type [NaiveMemoryStorageGraphSubscriber]: "
                        ).strip()
                        or "NaiveMemoryStorageGraphSubscriber"
                    )
                    try:
                        interval_str = (
                            input("Expected update interval seconds [5.0]: ").strip()
                            or "5.0"
                        )
                        interval = float(interval_str)
                    except ValueError:
                        interval = 5.0
                    config: Dict[str, Any] = {
                        "subscriber_type": sub_type,
                        "name": name,
                        "expected_update_interval": interval,
                    }
                    self.pretty_print(
                        "Registration Result", self.client.register_subscriber(config)
                    )
                elif choice == "11":
                    name = input("Subscriber name to unregister: ").strip()
                    if not name:
                        print("Name is required.")
                    else:
                        self.pretty_print(
                            "Unregistration Result",
                            self.client.unregister_subscriber(name),
                        )
                elif choice == "0":
                    print("Goodbye.")
                    return 0
                else:
                    print("Invalid option. Please choose a listed number.")

            except Exception as e:  # defensive: show friendly guidance
                print(f"\n❌ Error: {e}")
                print("Ensure the Witty Profiler server is running:")
                print("  witty-profiler")
                print("  # or: python -m witty_profiler")
                # continue loop for more attempts


def parse_args():
    parser = argparse.ArgumentParser(description="Interactive client for Witty Profiler API")
    parser.add_argument(
        "--host", default="localhost", help="Server host (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=18090, help="Server port (default: 18090)"
    )
    return parser.parse_args()


def example_client(host: str, port: int) -> ExampleClient:
    return ExampleClient(host=host, port=port).run()


def main():
    args = parse_args()
    return example_client(host=args.host, port=args.port)


if __name__ == "__main__":
    exit(main())
