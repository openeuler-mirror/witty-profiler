"""Concrete implementations of graph subscribers for various output destinations.

Provides ready-to-use subscribers for common output patterns: console logging,
in-memory storage, file persistence, and HTTP export.

Subscriber Implementations:
    - ConsoleGraphSubscriber: Print graph to logger (debugging)
    - NaiveMemoryStorageGraphSubscriber: Cache latest graph in memory
    - FileGraphDescSubscriber: Append graph description to file
    - HTTPGraphSubscriber: POST graph to HTTP endpoint (async)

Features:
    - Automatic periodic invocation via subscriber collection
    - Async HTTP requests don't block topology collection
    - In-memory storage for live querying of latest graph
    - File persistence for offline analysis
    - JSON serialization support

Usage:
    ```python
    # Console debugging
    console_sub = ConsoleGraphSubscriber()

    # Store latest graph
    memory_sub = NaiveMemoryStorageGraphSubscriber()
    latest = memory_sub.latest_graph  # Get cached result

    # File export
    file_sub = FileGraphDescSubscriber(
        dump_path="topology.txt",
        mode="a"  # Append mode
    )

    # HTTP export
    http_sub = HTTPGraphSubscriber(
        endpoint="http://localhost:18090/graph",
        async_notify=True  # Don't block collection loop
    )

    # Use in AnansiCore
    collection = SubscriberCollection(subscribers={
        "console": console_sub,
        "memory": memory_sub,
        "file": file_sub,
        "http": http_sub
    })
    ```

Notes:
    NaiveMemoryStorageGraphSubscriber is used by AnansiCore for get_last_graph().
    HTTP subscriber runs async to avoid blocking the collection loop.
    Graph serialization uses model_dump() for JSON compatibility.
"""

import json
from dataclasses import field
from typing import Optional

import requests

from anansi.common.logging import get_logger
from anansi.subscriber.subscribers import Graph, GraphSubscriber

LOGGER = get_logger(__name__)


class ConsoleGraphSubscriber(GraphSubscriber):
    """
    接收更新的图数据并打印到控制台
    """

    def _on_recv(self, target: Graph):
        LOGGER.info("Received updated graph:")
        LOGGER.info(target.describe())


class NaiveMemoryStorageGraphSubscriber(GraphSubscriber):
    """
    接收更新的图数据并保存到内存中
    """

    def __post_init__(self):
        super().__post_init__()
        self.latest_graph: Graph | None = None

    def _on_recv(self, target: Graph):
        self.latest_graph = target


class FileGraphDescSubscriber(GraphSubscriber):

    dump_path: str = "example.txt"
    mode: str = "a"  # 'a' for append, 'w' for write

    def __post_init__(self):
        super().__post_init__()
        if self.mode not in ["a", "w"]:
            raise ValueError("mode must be 'a' or 'w'")

    def _on_recv(self, entity: Graph):
        """
        接收更新的图数据并写入文件
        """
        with open(self.dump_path, self.mode) as f:
            f.write(entity.describe() + "\n")


class FileJsonGraphSubscriber(GraphSubscriber):

    dump_path: str = "example.json"
    mode: str = "a"  # 'a' for append, 'w' for write

    def __post_init__(self):
        super().__post_init__()
        if self.mode not in ["a", "w"]:
            raise ValueError("mode must be 'a' or 'w'")

    def _on_recv(self, target: Graph):
        """
        接收更新的图数据并以JSON格式写入文件
        """
        with open(self.dump_path, self.mode) as f:
            json.dump(target.model_dump(), f)
            f.write("\n")


class HttpPostGraphSubscriber(GraphSubscriber):
    """
    将图数据发送到HTTP服务器

    Example:
        >>> subscriber = HttpPostGraphSubscriber(
        ...     url="http://example.com/api/graphs",
        ...     post_attr={"headers": {"Authorization": "Bearer token"}}
        ... )
        >>> # This will send the graph data as JSON to the specified URL
    上面例子里，数据将按照{""data"": <graph_data>, ""headers"": {...}}的格式发送
    """

    url: str = field(default="")
    post_attr: dict = field(default_factory=dict)

    def _on_recv(self, target: Graph):
        """
        接收更新的图数据并发送到HTTP服务器
        """
        try:
            data = target.model_dump()
            data = {"data": data, **self.post_attr}
            response = requests.post(
                self.url,
                json=data,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            LOGGER.error(f"Connection error when sending graph data to {self.url}: {e}")
        except requests.exceptions.Timeout as e:
            LOGGER.error(f"Timeout error when sending graph data to {self.url}: {e}")
        except requests.exceptions.HTTPError as e:
            LOGGER.error(f"HTTP error when sending graph data to {self.url}: {e}")
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Request error when sending graph data to {self.url}: {e}")
        except Exception as e:
            LOGGER.error(f"Unexpected error when sending graph data to {self.url}: {e}")


try:
    from pymongo import MongoClient

    class MongoDBGraphSubscriber(GraphSubscriber):
        """
        向MongoDB数据库中写入图数据

        Attributes:
            connection_string (str): MongoDB连接字符串，默认为 "mongodb://localhost:27017/"
            database_name (str): 数据库名称，默认为 "graphs"
            collection_name (str): 集合名称，默认为 "graph_data"
            post_attr (dict): 额外的属性，将与图数据一起存储

        Example:
            ```python
            subscriber = MongoDBGraphSubscriber(
                connection_string="mongodb://localhost:27017/",
                database_name="my_graphs",
                collection_name="nodes_edges",
                post_attr={"source": "anansi", "version": "1.0"}
            )
            # This will store the graph data in the specified MongoDB collection
            ```
        """

        connection_string: str = field(default="mongodb://localhost:27017/")
        database_name: str = field(default="graphs")
        collection_name: str = field(default="graph_data")
        post_attr: dict = field(default_factory=dict)

        def __post_init__(self):
            super().__post_init__()
            try:
                self.client: MongoClient = MongoClient(self.connection_string)
                self.db = self.client[self.database_name]
                self.collection = self.db[self.collection_name]
            except Exception as e:
                LOGGER.error(
                    f"Failed to connect to MongoDB at {self.connection_string}: {e}"
                )
                raise

        def _on_recv(self, target: Graph):
            """
            接收更新的图数据并存储到MongoDB
            """
            try:
                # Create document combining graph data and additional attributes
                document = target.model_dump()
                document.update(self.post_attr)

                # Insert into MongoDB collection
                result = self.collection.insert_one(document)
                LOGGER.info(
                    f"Successfully inserted graph data into MongoDB with ID: {result.inserted_id}"
                )
            except Exception as e:
                LOGGER.error(f"Failed to insert graph data into MongoDB: {e}")

except ImportError:
    LOGGER.info(
        "pymongo is not installed. MongoDBGraphSubscriber will not be available."
    )

__all__ = [
    "ConsoleGraphSubscriber",
    "FileGraphDescSubscriber",
    "FileJsonGraphSubscriber",
    "HttpPostGraphSubscriber",
]
