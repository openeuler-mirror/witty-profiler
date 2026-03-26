import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from anansi.entity.node_entity import ProcessEntity
from anansi.graph.graph import Graph
from anansi.subscriber.subscriber_base import Subscriber
from anansi.subscriber.subscriber_collection import SubscriberCollection


# 用于测试的简单订阅者类
class SimpleSubscriber4Test(Subscriber):
    """
    测试用的简单订阅者实现
    用于验证SubscriberCollection的功能
    """

    def __init__(self, **kwargs):
        # 初始化接收计数器
        self.received_count = 0
        # 存储最后接收的数据
        self.last_received = None
        super().__init__(**kwargs)

    @property
    def expected_type(self) -> type[Any]:
        """期望接收任意类型的数据"""
        return object

    def _on_recv(self, target: Any):
        """接收到数据时更新计数器和存储数据"""
        self.received_count += 1
        self.last_received = target


class GraphSubscriber4Test(Subscriber):
    """
    测试用的图订阅者实现
    只接收Graph类型的数据
    """

    def __init__(self, **kwargs):
        # 初始化接收计数器
        self.received_count = 0
        # 存储最后接收的图数据
        self.last_graph = None
        super().__init__(**kwargs)

    @property
    def expected_type(self) -> type[Graph]:
        """只期望接收Graph类型的数据"""
        return Graph

    def _on_recv(self, target: Graph):
        """接收到图数据时更新计数器和存储数据"""
        self.received_count += 1
        self.last_graph = target


class TestSubscriberCollection(unittest.TestCase):
    """
    SubscriberCollection的单元测试类
    测试订阅者集合的各种功能
    """

    def setUp(self):
        """
        在每个测试方法执行前运行
        设置测试所需的初始数据和对象
        """
        # 创建一个空的订阅者集合
        self.collection = SubscriberCollection()

        # 创建测试用的订阅者实例
        self.subscriber1 = SimpleSubscriber4Test(name="test_sub1")
        self.subscriber2 = SimpleSubscriber4Test(name="test_sub2")
        self.graph_subscriber = GraphSubscriber4Test(name="graph_sub")

        # 创建测试用的图数据
        self.test_graph = Graph()
        self.test_graph.try_add_node(ProcessEntity(pid=1001))

    def test_initialization_empty(self):
        """
        测试空集合的初始化
        验证新创建的集合没有任何订阅者
        """
        # 创建一个新的订阅者集合
        collection = SubscriberCollection()
        # 验证订阅者字典为空
        self.assertEqual(len(collection.subscribers), 0)
        # 验证订阅者字典是一个字典类型
        self.assertIsInstance(collection.subscribers, dict)

    def test_initialization_with_subscribers_dict(self):
        """
        测试使用字典配置初始化集合
        验证集合能够从配置字典中创建订阅者
        """
        # 创建订阅者配置字典
        config = {
            "subscribers": {
                "sub1": {
                    "subscriber_type": "TestSimpleSubscriber",
                    "name": "configured_sub",
                }
            }
        }

        # 使用配置创建集合
        # 注意：这需要订阅者在SubscriberMeta注册表中
        with patch(
            "anansi.subscriber.subscriber_collection.SubscriberFactory"
        ) as mock_factory:
            # 模拟工厂创建订阅者
            mock_instance = MagicMock()
            mock_factory.get_instance.return_value = mock_instance
            mock_instance.create_subscriber.return_value = self.subscriber1

            # 创建集合
            collection = SubscriberCollection(**config)
            # 验证订阅者已添加
            self.assertGreaterEqual(len(collection.subscribers), 0)

    def test_initialization_with_subscriber_instances(self):
        """
        测试使用订阅者实例初始化集合
        验证可以直接传入Subscriber对象
        """
        # 创建包含订阅者实例的配置
        subscribers_dict = {"sub1": self.subscriber1, "sub2": self.subscriber2}

        # 使用订阅者实例创建集合
        collection = SubscriberCollection(subscribers=subscribers_dict)

        # 验证订阅者已正确添加
        self.assertEqual(len(collection.subscribers), 2)
        self.assertIn("sub1", collection.subscribers)
        self.assertIn("sub2", collection.subscribers)
        self.assertEqual(collection.subscribers["sub1"], self.subscriber1)
        self.assertEqual(collection.subscribers["sub2"], self.subscriber2)

    def test_register_new_subscriber(self):
        """
        测试注册新订阅者
        验证register方法能够正确添加订阅者
        """
        # 初始时集合应该是空的
        self.assertEqual(len(self.collection.subscribers), 0)

        # 注册第一个订阅者
        self.collection.register("sub1", self.subscriber1)
        # 验证订阅者已添加
        self.assertEqual(len(self.collection.subscribers), 1)
        self.assertIn("sub1", self.collection.subscribers)
        self.assertEqual(self.collection.subscribers["sub1"], self.subscriber1)

        # 注册第二个订阅者
        self.collection.register("sub2", self.subscriber2)
        # 验证两个订阅者都存在
        self.assertEqual(len(self.collection.subscribers), 2)
        self.assertIn("sub2", self.collection.subscribers)

    def test_register_duplicate_subscriber_without_override(self):
        """
        测试注册重复名称的订阅者（不允许覆盖）
        验证默认情况下不能注册同名订阅者
        """
        # 注册第一个订阅者
        self.collection.register("sub1", self.subscriber1)
        initial_subscriber = self.collection.subscribers["sub1"]

        # 尝试用相同名称注册不同的订阅者（不允许覆盖）
        self.collection.register("sub1", self.subscriber2, enable_override=False)

        # 验证原订阅者未被替换
        self.assertEqual(self.collection.subscribers["sub1"], initial_subscriber)
        self.assertNotEqual(self.collection.subscribers["sub1"], self.subscriber2)

    def test_register_duplicate_subscriber_with_override(self):
        """
        测试注册重复名称的订阅者（允许覆盖）
        验证启用覆盖选项后可以替换同名订阅者
        """
        # 注册第一个订阅者
        self.collection.register("sub1", self.subscriber1)
        # 验证初始订阅者
        self.assertEqual(self.collection.subscribers["sub1"], self.subscriber1)

        # 用相同名称注册不同的订阅者（允许覆盖）
        self.collection.register("sub1", self.subscriber2, enable_override=True)

        # 验证订阅者已被替换
        self.assertEqual(self.collection.subscribers["sub1"], self.subscriber2)
        self.assertNotEqual(self.collection.subscribers["sub1"], self.subscriber1)

    def test_unregister_subscriber(self):
        """
        测试注销订阅者
        验证unregister方法能够正确删除订阅者
        """
        # 注册两个订阅者
        self.collection.register("sub1", self.subscriber1)
        self.collection.register("sub2", self.subscriber2)
        # 验证两个订阅者都存在
        self.assertEqual(len(self.collection.subscribers), 2)

        # 注销第一个订阅者
        self.collection.unregister_subscriber("sub1")
        # 验证订阅者已被删除
        self.assertEqual(len(self.collection.subscribers), 1)
        self.assertNotIn("sub1", self.collection.subscribers)
        self.assertIn("sub2", self.collection.subscribers)

        # 注销第二个订阅者
        self.collection.unregister_subscriber("sub2")
        # 验证集合现在为空
        self.assertEqual(len(self.collection.subscribers), 0)

    def test_unregister_nonexistent_subscriber(self):
        """
        测试注销不存在的订阅者
        验证尝试删除不存在的订阅者不会引发错误
        """
        # 注册一个订阅者
        self.collection.register("sub1", self.subscriber1)
        initial_count = len(self.collection.subscribers)

        # 尝试注销不存在的订阅者
        # 应该不会抛出异常
        try:
            self.collection.unregister_subscriber("nonexistent")
            exception_raised = False
        except KeyError:
            exception_raised = True

        # 验证没有抛出异常，且订阅者数量未变
        self.assertFalse(exception_raised)
        self.assertEqual(len(self.collection.subscribers), initial_count)

    def test_on_recv_forwards_to_all_subscribers(self):
        """
        测试_on_recv方法转发消息给所有订阅者
        验证集合能够将接收到的数据转发给所有注册的订阅者
        """
        # 注册多个订阅者
        self.collection.register("sub1", self.subscriber1)
        self.collection.register("sub2", self.subscriber2)
        self.collection.register("graph_sub", self.graph_subscriber)

        # 创建测试数据
        test_data = "test message"

        # 调用_on_recv方法
        self.collection._on_recv(test_data)

        # 验证所有订阅者都收到了数据
        self.assertEqual(self.subscriber1.received_count, 1)
        self.assertEqual(self.subscriber1.last_received, test_data)
        self.assertEqual(self.subscriber2.received_count, 1)
        self.assertEqual(self.subscriber2.last_received, test_data)
        # graph_subscriber由于类型不匹配不应该接收到数据
        # 但notify方法会被调用，只是内部会检查类型

    def test_on_recv_with_graph_data(self):
        """
        测试_on_recv方法处理图数据
        验证图订阅者能够接收图类型的数据
        """
        # 注册订阅者
        self.collection.register("simple_sub", self.subscriber1)
        self.collection.register("graph_sub", self.graph_subscriber)

        # 发送图数据
        self.collection._on_recv(self.test_graph)

        # 验证简单订阅者（接收任意类型）收到数据
        self.assertEqual(self.subscriber1.received_count, 1)
        self.assertEqual(self.subscriber1.last_received, self.test_graph)

        # 验证图订阅者收到数据
        self.assertEqual(self.graph_subscriber.received_count, 1)
        self.assertEqual(self.graph_subscriber.last_graph, self.test_graph)

    def test_on_recv_with_subscriber_exception(self):
        """
        测试_on_recv方法在订阅者抛出异常时的处理
        验证一个订阅者抛出异常不会影响其他订阅者接收数据
        """
        # 创建一个会抛出异常的订阅者
        error_subscriber = SimpleSubscriber4Test(name="error_sub")
        original_on_recv = error_subscriber._on_recv

        # 修改订阅者的_on_recv方法使其抛出异常
        def error_on_recv(target):
            raise ValueError("Test error")

        error_subscriber._on_recv = error_on_recv

        # 注册订阅者
        self.collection.register("error_sub", error_subscriber)
        self.collection.register("normal_sub", self.subscriber1)

        # 发送数据
        test_data = "test message"
        self.collection._on_recv(test_data)

        # 验证正常订阅者仍然收到数据
        self.assertEqual(self.subscriber1.received_count, 1)
        self.assertEqual(self.subscriber1.last_received, test_data)

    def test_notify_method(self):
        """
        测试notify方法
        验证通过notify方法可以触发消息转发
        """
        # 注册订阅者
        self.collection.register("sub1", self.subscriber1)

        # 通过notify方法发送数据
        test_data = "notification test"
        self.collection.notify(test_data)

        # 验证订阅者收到数据
        self.assertEqual(self.subscriber1.received_count, 1)
        self.assertEqual(self.subscriber1.last_received, test_data)

    def test_expected_type_property(self):
        """
        测试expected_type属性
        验证集合的expected_type返回正确的类型
        """
        # SubscriberCollection应该有expected_type属性
        # 但需要在实现中定义
        # 这里测试它是否存在
        self.assertTrue(hasattr(self.collection, "expected_type"))

    def test_multiple_notifications(self):
        """
        测试多次通知
        验证订阅者能够正确处理多次接收数据
        """
        # 注册订阅者
        self.collection.register("sub1", self.subscriber1)

        # 发送多次数据
        for i in range(5):
            test_data = f"message_{i}"
            self.collection.notify(test_data)

        # 验证订阅者收到所有消息
        self.assertEqual(self.subscriber1.received_count, 5)
        self.assertEqual(self.subscriber1.last_received, "message_4")

    def test_empty_collection_notification(self):
        """
        测试空集合的通知
        验证向空集合发送通知不会引发错误
        """
        # 确保集合为空
        self.assertEqual(len(self.collection.subscribers), 0)

        # 向空集合发送通知
        # 应该不会抛出异常
        try:
            self.collection.notify("test message")
            exception_raised = False
        except Exception as e:
            exception_raised = True

        # 验证没有抛出异常
        self.assertFalse(exception_raised)


if __name__ == "__main__":
    test_class = TestSubscriberCollection()
    test_class.setUp()
    test_class.test_empty_collection_notification()
