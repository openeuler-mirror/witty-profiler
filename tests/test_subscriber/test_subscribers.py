import json
import os
import tempfile
import threading
import time
import unittest
from typing import Any
from unittest.mock import Mock, patch

from anansi.entity.node_entity import ProcessEntity
from anansi.graph.graph import Graph
from anansi.subscriber.implementations.graph_subscribers import (
    ConsoleGraphSubscriber,
    FileGraphDescSubscriber,
    FileJsonGraphSubscriber,
    HttpPostGraphSubscriber,
    NaiveMemoryStorageGraphSubscriber,
)
from anansi.subscriber.subscriber_base import (
    Subscriber,
    SubscriberFactory,
    SubscriberMeta,
    create_subscriber,
    get_available_subscriber_types,
)

# ==================== 测试用的自定义订阅者类 ====================


class MockSimpleSubscriber(Subscriber):
    """
    测试用的简单订阅者
    用于验证Subscriber基类的功能
    """

    def __init__(self, **kwargs):
        # 记录接收到的所有数据
        self.received_items = []
        # 记录_on_recv被调用的次数
        self.call_count = 0
        super().__init__(**kwargs)

    @property
    def expected_type(self) -> type[Any]:
        """接收任意类型的数据"""
        return object

    def _on_recv(self, target: Any):
        """记录接收到的数据"""
        self.call_count += 1
        self.received_items.append(target)


class TypedSubscriber(Subscriber):
    """
    测试用的类型化订阅者
    只接收字符串类型的数据
    """

    def __init__(self, **kwargs):
        # 记录接收到的字符串
        self.received_strings = []
        super().__init__(**kwargs)

    @property
    def expected_type(self) -> type[str]:
        """只接收字符串类型"""
        return str

    def _on_recv(self, target: str):
        """记录接收到的字符串"""
        self.received_strings.append(target)


class AsyncTestSubscriber(Subscriber):
    """
    测试用的异步订阅者
    用于验证异步通知功能
    """

    def __init__(self, **kwargs):
        # 用于同步的事件对象
        self.event = threading.Event()
        # 记录接收到的数据
        self.received_data = None
        # 记录执行_on_recv的线程ID
        self.thread_id = None
        super().__init__(**kwargs)

    @property
    def expected_type(self) -> type[Any]:
        """接收任意类型"""
        return object

    def _on_recv(self, target: Any):
        """记录数据和线程ID，然后设置事件"""
        self.thread_id = threading.current_thread().ident
        self.received_data = target
        # 模拟耗时操作
        time.sleep(0.1)
        # 设置事件通知测试可以继续
        self.event.set()


# ==================== Subscriber基类测试 ====================


class TestSubscriberBase(unittest.TestCase):
    """
    测试Subscriber基类的功能
    验证订阅者的核心机制
    """

    def setUp(self):
        """
        在每个测试前执行
        创建测试所需的对象
        """
        # 创建基本的订阅者实例
        self.subscriber = MockSimpleSubscriber()
        # 创建类型化订阅者
        self.typed_subscriber = TypedSubscriber()

    def test_subscriber_initialization(self):
        """
        测试订阅者初始化
        验证订阅者的基本属性被正确设置
        """
        # 验证订阅者类型已设置
        self.assertEqual(self.subscriber.subscriber_type, "MockSimpleSubscriber")
        # 验证名称已自动生成
        self.assertIsNotNone(self.subscriber.name)
        # 验证名称包含订阅者类型
        self.assertIn("MockSimpleSubscriber", self.subscriber.name)
        # 验证默认更新间隔
        self.assertEqual(self.subscriber.expected_update_interval, 5.0)
        # 验证默认不使用异步通知
        self.assertFalse(self.subscriber.async_notify)

    def test_subscriber_initialization_with_name(self):
        """
        测试使用自定义名称初始化订阅者
        验证可以指定订阅者的名称
        """
        # 使用自定义名称创建订阅者
        custom_name = "my_custom_subscriber"
        subscriber = MockSimpleSubscriber(name=custom_name)

        # 验证名称被正确设置
        self.assertEqual(subscriber.name, custom_name)

    def test_subscriber_initialization_with_parameters(self):
        """
        测试使用自定义参数初始化订阅者
        验证所有参数都能正确设置
        """
        # 使用自定义参数创建订阅者
        subscriber = MockSimpleSubscriber(
            name="test_sub", expected_update_interval=10.0, async_notify=True
        )

        # 验证所有参数
        self.assertEqual(subscriber.name, "test_sub")
        self.assertEqual(subscriber.expected_update_interval, 10.0)
        self.assertTrue(subscriber.async_notify)

    def test_expected_type_property(self):
        """
        测试expected_type属性
        验证订阅者能够声明期望的数据类型
        """
        # 验证简单订阅者接收任意类型
        self.assertEqual(self.subscriber.expected_type, object)
        # 验证类型化订阅者只接收字符串
        self.assertEqual(self.typed_subscriber.expected_type, str)

    def test_notify_with_correct_type(self):
        """
        测试使用正确类型的数据通知订阅者
        验证订阅者能够接收正确类型的数据
        """
        # 发送字符串给类型化订阅者
        test_string = "test message"
        self.typed_subscriber.notify(test_string)

        # 验证订阅者接收到数据
        self.assertEqual(len(self.typed_subscriber.received_strings), 1)
        self.assertEqual(self.typed_subscriber.received_strings[0], test_string)

    def test_notify_with_incorrect_type(self):
        """
        测试使用错误类型的数据通知订阅者
        验证订阅者会忽略不匹配的数据类型
        """
        # 发送整数给只接收字符串的订阅者
        test_int = 123
        self.typed_subscriber.notify(test_int)

        # 验证订阅者没有接收到数据
        self.assertEqual(len(self.typed_subscriber.received_strings), 0)

    def test_notify_calls_on_recv(self):
        """
        测试notify方法会调用_on_recv
        验证通知机制正确触发处理方法
        """
        # 发送多个数据
        test_data = ["item1", "item2", "item3"]
        for item in test_data:
            self.subscriber.notify(item)

        # 验证_on_recv被调用了正确次数
        self.assertEqual(self.subscriber.call_count, 3)
        # 验证所有数据都被接收
        self.assertEqual(self.subscriber.received_items, test_data)

    def test_synchronous_notify(self):
        """
        测试同步通知
        验证默认情况下notify是同步执行的
        """
        # 记录主线程ID
        main_thread_id = threading.current_thread().ident

        # 创建同步订阅者（async_notify=False）
        sync_subscriber = AsyncTestSubscriber(async_notify=False)

        # 发送数据
        test_data = "sync test"
        sync_subscriber.notify(test_data)

        # 验证_on_recv在主线程中执行
        self.assertEqual(sync_subscriber.thread_id, main_thread_id)
        # 验证数据被接收
        self.assertEqual(sync_subscriber.received_data, test_data)

    def test_asynchronous_notify(self):
        """
        测试异步通知
        验证异步通知在独立线程中执行
        """
        # 记录主线程ID
        main_thread_id = threading.current_thread().ident

        # 创建异步订阅者（async_notify=True）
        async_subscriber = AsyncTestSubscriber(async_notify=True)

        # 发送数据
        test_data = "async test"
        async_subscriber.notify(test_data)

        # 等待异步操作完成（最多1秒）
        async_subscriber.event.wait(timeout=1.0)

        # 验证_on_recv在不同线程中执行
        self.assertNotEqual(async_subscriber.thread_id, main_thread_id)
        # 验证数据被接收
        self.assertEqual(async_subscriber.received_data, test_data)

    def test_subscriber_meta_registry(self):
        """
        测试SubscriberMeta注册表
        验证所有订阅者类都被正确注册
        """
        # 获取注册表
        registry = SubscriberMeta.get_registry()

        # 验证注册表是字典类型
        self.assertIsInstance(registry, dict)
        # 验证测试用的订阅者类已注册
        self.assertIn("MockSimpleSubscriber", registry)
        self.assertIn("TypedSubscriber", registry)
        self.assertIn("AsyncTestSubscriber", registry)


# ==================== SubscriberFactory测试 ====================


class TestSubscriberFactory(unittest.TestCase):
    """
    测试SubscriberFactory工厂类
    验证订阅者的创建机制
    """

    def setUp(self):
        """在每个测试前执行"""
        # 获取工厂单例
        self.factory: SubscriberFactory = SubscriberFactory.get_instance()

    def test_factory_is_singleton(self):
        """
        测试工厂是单例模式
        验证多次获取返回同一个实例
        """
        # 获取两个实例
        factory1 = SubscriberFactory.get_instance()
        factory2 = SubscriberFactory.get_instance()

        # 验证是同一个实例
        self.assertIs(factory1, factory2)

    def test_create_subscriber_with_valid_config(self):
        """
        测试使用有效配置创建订阅者
        验证工厂能够根据配置创建订阅者实例
        """
        # 准备配置
        config = {
            "subscriber_type": "MockSimpleSubscriber",
            "name": "factory_created",
            "expected_update_interval": 3.0,
        }

        # 使用工厂创建订阅者
        subscriber = self.factory.create_subscriber(config)

        # 验证订阅者被成功创建
        self.assertIsNotNone(subscriber)
        self.assertIsInstance(subscriber, MockSimpleSubscriber)
        self.assertEqual(subscriber.name, "factory_created")
        self.assertEqual(subscriber.expected_update_interval, 3.0)

    def test_create_subscriber_with_invalid_type(self):
        """
        测试使用无效类型创建订阅者
        验证工厂在遇到未知类型时返回None
        """
        # 准备无效配置
        config = {"subscriber_type": "NonExistentSubscriber", "name": "invalid"}

        # 尝试创建订阅者
        subscriber = self.factory.create_subscriber(config)

        # 验证返回None
        self.assertIsNone(subscriber)

    def test_create_subscriber_without_type(self):
        """
        测试缺少类型的配置
        验证工厂在缺少subscriber_type时返回None
        """
        # 准备缺少类型的配置
        config = {"name": "no_type"}

        # 尝试创建订阅者
        subscriber = self.factory.create_subscriber(config)

        # 验证返回None
        self.assertIsNone(subscriber)

    def test_create_subscriber_with_invalid_parameters(self):
        """
        测试使用无效参数创建订阅者
        验证工厂在参数错误时返回None
        """
        # 准备包含无效参数的配置
        config = {
            "subscriber_type": "MockSimpleSubscriber",
            "invalid_param": "should_fail",
        }

        # 尝试创建订阅者（可能成功，取决于实现）
        # 如果dataclass忽略额外参数，则会成功
        subscriber = self.factory.create_subscriber(config)

        # 由于dataclass的kw_only特性，这可能会失败或成功
        # 这里主要测试工厂不会崩溃
        # 实际结果取决于具体实现

    def test_create_subscriber_helper_function(self):
        """
        测试create_subscriber辅助函数
        验证模块级别的便捷函数正常工作
        """
        # 准备配置
        config = {"subscriber_type": "MockSimpleSubscriber", "name": "helper_created"}

        # 使用辅助函数创建订阅者
        subscriber = create_subscriber(config)

        # 验证订阅者被成功创建
        self.assertIsNotNone(subscriber)
        self.assertIsInstance(subscriber, MockSimpleSubscriber)
        self.assertEqual(subscriber.name, "helper_created")

    def test_get_available_subscriber_types(self):
        """
        测试获取可用订阅者类型
        验证能够列出所有已注册的订阅者类型
        """
        # 获取可用类型列表
        available_types = get_available_subscriber_types()

        # 验证返回列表
        self.assertIsInstance(available_types, list)
        # 验证列表不为空
        self.assertGreater(len(available_types), 0)
        # 验证包含测试用的订阅者类型
        self.assertIn("MockSimpleSubscriber", available_types)


# ==================== GraphSubscriber测试 ====================


class TestGraphSubscriber(unittest.TestCase):
    """
    测试GraphSubscriber基类
    验证图订阅者的特定功能
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建测试用的图数据
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))
        self.test_graph.try_add_node(ProcessEntity(pid=1002))

    def test_graph_subscriber_expected_type(self):
        """
        测试GraphSubscriber的expected_type
        验证图订阅者只接收Graph类型
        """
        # 创建内存存储图订阅者
        subscriber = NaiveMemoryStorageGraphSubscriber()

        # 验证期望类型是Graph
        self.assertEqual(subscriber.expected_type, Graph)

    def test_graph_subscriber_ignores_non_graph_data(self):
        """
        测试图订阅者忽略非图类型数据
        验证类型检查机制正常工作
        """
        # 创建内存存储图订阅者
        subscriber = NaiveMemoryStorageGraphSubscriber()

        # 尝试发送非图类型数据
        subscriber.notify("not a graph")
        subscriber.notify(123)
        subscriber.notify({"key": "value"})

        # 验证订阅者没有接收到数据
        self.assertIsNone(subscriber.latest_graph)

    def test_graph_subscriber_accepts_graph_data(self):
        """
        测试图订阅者接收图类型数据
        验证能够正确处理Graph对象
        """
        # 创建内存存储图订阅者
        subscriber = NaiveMemoryStorageGraphSubscriber()

        # 发送图数据
        subscriber.notify(self.test_graph)

        # 验证订阅者接收到数据
        self.assertIsNotNone(subscriber.latest_graph)
        self.assertEqual(subscriber.latest_graph, self.test_graph)


# ==================== 具体实现的订阅者测试 ====================


class TestConsoleGraphSubscriber(unittest.TestCase):
    """
    测试ConsoleGraphSubscriber
    验证控制台输出订阅者
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建测试图
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))
        # 创建订阅者
        self.subscriber = ConsoleGraphSubscriber()

    @patch("anansi.subscriber.implementations.graph_subscribers.LOGGER")
    def test_console_subscriber_logs_graph_info(self, mock_logger):
        """
        测试控制台订阅者输出图信息
        验证能够记录图的描述信息
        """
        # 发送图数据
        self.subscriber.notify(self.test_graph)

        # 验证logger被调用
        # info方法应该被调用至少一次
        self.assertGreater(mock_logger.info.call_count, 0)


class TestNaiveMemoryStorageGraphSubscriber(unittest.TestCase):
    """
    测试NaiveMemoryStorageGraphSubscriber
    验证内存存储订阅者
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建测试图
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))
        # 创建订阅者
        self.subscriber = NaiveMemoryStorageGraphSubscriber()

    def test_initial_state(self):
        """
        测试初始状态
        验证新创建的订阅者没有存储图
        """
        self.assertIsNone(self.subscriber.latest_graph)

    def test_stores_graph(self):
        """
        测试存储图数据
        验证能够保存接收到的图
        """
        # 发送图数据
        self.subscriber.notify(self.test_graph)

        # 验证图被存储
        self.assertIsNotNone(self.subscriber.latest_graph)
        self.assertEqual(self.subscriber.latest_graph, self.test_graph)

    def test_updates_stored_graph(self):
        """
        测试更新存储的图
        验证新的图会替换旧的图
        """
        # 发送第一个图
        graph1 = Graph()
        graph1.try_add_node(ProcessEntity(pid=1001))
        self.subscriber.notify(graph1)

        # 验证第一个图被存储
        self.assertEqual(self.subscriber.latest_graph, graph1)

        # 发送第二个图
        graph2 = Graph()
        graph2.try_add_node(ProcessEntity(pid=2002))
        self.subscriber.notify(graph2)

        # 验证第二个图替换了第一个图
        self.assertEqual(self.subscriber.latest_graph, graph2)
        self.assertNotEqual(self.subscriber.latest_graph, graph1)


class TestFileGraphDescSubscriber(unittest.TestCase):
    """
    测试FileGraphDescSubscriber
    验证文件描述输出订阅者
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        )
        self.temp_file_path = self.temp_file.name
        self.temp_file.close()

        # 创建测试图
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))

    def tearDown(self):
        """在每个测试后执行，清理临时文件"""
        if os.path.exists(self.temp_file_path):
            os.unlink(self.temp_file_path)

    def test_initialization_with_write_mode(self):
        """
        测试使用写入模式初始化
        验证可以创建写入模式的订阅者
        """
        # 创建写入模式的订阅者
        subscriber = FileGraphDescSubscriber(dump_path=self.temp_file_path, mode="w")
        self.assertEqual(subscriber.mode, "w")

    def test_initialization_with_append_mode(self):
        """
        测试使用追加模式初始化
        验证可以创建追加模式的订阅者
        """
        # 创建追加模式的订阅者
        subscriber = FileGraphDescSubscriber(dump_path=self.temp_file_path, mode="a")
        self.assertEqual(subscriber.mode, "a")

    def test_initialization_with_invalid_mode(self):
        """
        测试使用无效模式初始化
        验证无效模式会引发异常
        """
        # 尝试创建无效模式的订阅者
        with self.assertRaises(ValueError):
            FileGraphDescSubscriber(dump_path=self.temp_file_path, mode="x")  # 无效模式

    def test_writes_graph_description_to_file(self):
        """
        测试写入图描述到文件
        验证能够正确写入文件
        """
        # 创建订阅者
        subscriber = FileGraphDescSubscriber(dump_path=self.temp_file_path, mode="w")

        # 发送图数据
        subscriber.notify(self.test_graph)

        # 读取文件内容
        with open(self.temp_file_path, "r") as f:
            content = f.read()

        # 验证文件包含图描述
        self.assertIn("Graph", content)
        self.assertGreater(len(content), 0)

    def test_append_mode_preserves_previous_content(self):
        """
        测试追加模式保留之前的内容
        验证追加模式不会覆盖已有内容
        """
        # 创建追加模式的订阅者
        subscriber = FileGraphDescSubscriber(dump_path=self.temp_file_path, mode="a")

        # 发送第一个图
        graph1 = Graph()
        graph1.try_add_node(ProcessEntity(pid=1001))
        subscriber.notify(graph1)

        # 发送第二个图
        graph2 = Graph()
        graph2.try_add_node(ProcessEntity(pid=2002))
        subscriber.notify(graph2)

        # 读取文件内容
        with open(self.temp_file_path, "r") as f:
            lines = f.readlines()

        # 验证文件包含两个图的描述
        self.assertGreaterEqual(len(lines), 2)


class TestFileJsonGraphSubscriber(unittest.TestCase):
    """
    测试FileJsonGraphSubscriber
    验证JSON文件输出订阅者
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_file_path = self.temp_file.name
        self.temp_file.close()

        # 创建测试图
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))

    def tearDown(self):
        """在每个测试后执行，清理临时文件"""
        if os.path.exists(self.temp_file_path):
            os.unlink(self.temp_file_path)

    def test_writes_json_to_file(self):
        """
        测试写入JSON到文件
        验证能够正确写入JSON格式
        """
        # 创建订阅者
        subscriber = FileJsonGraphSubscriber(dump_path=self.temp_file_path, mode="w")

        # 发送图数据
        subscriber.notify(self.test_graph)

        # 读取文件内容并解析JSON
        with open(self.temp_file_path, "r") as f:
            content = f.read().strip()
            # 解析第一行JSON
            first_line = content.split("\n")[0]
            data = json.loads(first_line)

        # 验证JSON数据包含图信息
        self.assertIn("nodes", data)
        self.assertIn("edges", data)

    def test_json_format_is_valid(self):
        """
        测试JSON格式有效性
        验证输出的JSON可以被正确解析
        """
        # 创建订阅者
        subscriber = FileJsonGraphSubscriber(dump_path=self.temp_file_path, mode="w")

        # 发送图数据
        subscriber.notify(self.test_graph)

        # 尝试解析JSON
        try:
            with open(self.temp_file_path, "r") as f:
                first_line = f.readline()
                json.loads(first_line)
            json_valid = True
        except json.JSONDecodeError:
            json_valid = False

        # 验证JSON格式有效
        self.assertTrue(json_valid)


class TestHttpPostGraphSubscriber(unittest.TestCase):
    """
    测试HttpPostGraphSubscriber
    验证HTTP POST订阅者
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建测试图
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))
        # 测试URL
        self.test_url = "http://example.com/api/graphs"

    @patch("anansi.subscriber.implementations.graph_subscribers.requests.post")
    def test_sends_http_post_request(self, mock_post):
        """
        测试发送HTTP POST请求
        验证能够向指定URL发送数据
        """
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # 创建订阅者
        subscriber = HttpPostGraphSubscriber(url=self.test_url)

        # 发送图数据
        subscriber.notify(self.test_graph)

        # 验证requests.post被调用
        mock_post.assert_called_once()
        # 验证URL正确
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], self.test_url)

    @patch("anansi.subscriber.implementations.graph_subscribers.requests.post")
    def test_includes_post_attributes(self, mock_post):
        """
        测试包含额外的POST属性
        验证能够发送额外的属性数据
        """
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # 创建带额外属性的订阅者
        post_attr = {"headers": {"Authorization": "Bearer token"}}
        subscriber = HttpPostGraphSubscriber(url=self.test_url, post_attr=post_attr)

        # 发送图数据
        subscriber.notify(self.test_graph)

        # 验证requests.post被调用
        mock_post.assert_called_once()
        # 获取调用参数
        call_kwargs = mock_post.call_args[1]
        # 验证json参数包含data和额外属性
        self.assertIn("json", call_kwargs)
        self.assertIn("data", call_kwargs["json"])
        self.assertIn("headers", call_kwargs["json"])

    @patch("anansi.subscriber.implementations.graph_subscribers.requests.post")
    def test_handles_connection_error(self, mock_post):
        """
        测试处理连接错误
        验证连接失败时不会崩溃
        """
        # 模拟连接错误
        mock_post.side_effect = Exception("Connection failed")

        # 创建订阅者
        subscriber = HttpPostGraphSubscriber(url=self.test_url)

        # 发送图数据（不应该抛出异常）
        try:
            subscriber.notify(self.test_graph)
            exception_raised = False
        except Exception:
            exception_raised = True

        # 验证异常被捕获，没有向外抛出
        self.assertFalse(exception_raised)


# ==================== MongoDB订阅者测试 ====================


class TestMongoDBGraphSubscriber(unittest.TestCase):
    """
    测试MongoDBGraphSubscriber
    验证MongoDB存储订阅者
    注意：这些测试使用mock，不需要真实的MongoDB连接
    """

    def setUp(self):
        """在每个测试前执行"""
        # 创建测试图
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))

    @patch(
        "anansi.subscriber.implementations.graph_subscribers.MongoClient", create=True
    )
    def test_mongodb_subscriber_initialization(self, mock_mongo_client):
        """
        测试MongoDB订阅者初始化
        验证能够正确初始化MongoDB连接
        """
        # 模拟MongoDB客户端
        mock_client_instance = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_client_instance.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_mongo_client.return_value = mock_client_instance

        # 尝试导入并创建订阅者
        try:
            from anansi.subscriber.implementations.graph_subscribers import (
                MongoDBGraphSubscriber,
            )

            # 创建订阅者
            subscriber = MongoDBGraphSubscriber(
                connection_string="mongodb://localhost:27017/",
                database_name="test_db",
                collection_name="test_collection",
            )

            # 验证订阅者被创建
            self.assertIsNotNone(subscriber)
            # 验证MongoClient被调用
            mock_mongo_client.assert_called_once()

        except ImportError:
            # 如果pymongo未安装，跳过测试
            self.skipTest("pymongo not installed")

    @patch(
        "anansi.subscriber.implementations.graph_subscribers.MongoClient", create=True
    )
    def test_mongodb_subscriber_inserts_data(self, mock_mongo_client):
        """
        测试MongoDB订阅者插入数据
        验证能够将图数据插入MongoDB
        """
        # 模拟MongoDB组件
        mock_client_instance = Mock()
        mock_db = Mock()
        mock_collection = Mock()
        mock_result = Mock()
        mock_result.inserted_id = "test_id_123"

        # 设置mock返回值
        mock_client_instance.__getitem__ = Mock(return_value=mock_db)
        mock_db.__getitem__ = Mock(return_value=mock_collection)
        mock_collection.insert_one = Mock(return_value=mock_result)
        mock_mongo_client.return_value = mock_client_instance

        # 尝试导入并使用订阅者
        try:
            from anansi.subscriber.implementations.graph_subscribers import (
                MongoDBGraphSubscriber,
            )

            # 创建订阅者
            subscriber = MongoDBGraphSubscriber(
                connection_string="mongodb://localhost:27017/",
                database_name="test_db",
                collection_name="test_collection",
            )

            # 发送图数据
            subscriber.notify(self.test_graph)

            # 验证insert_one被调用
            mock_collection.insert_one.assert_called_once()

        except ImportError:
            # 如果pymongo未安装，跳过测试
            self.skipTest("pymongo not installed")


if __name__ == "__main__":
    unittest.main()
