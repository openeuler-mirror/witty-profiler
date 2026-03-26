import threading
import time
import unittest

from anansi.common.constants import DEFAULT_NAMESPACE
from anansi.common.env_manager import EnvInfo
from anansi.entity.entity_namespace import EntityNameSpace


def make_env(local_ip: str) -> EnvInfo:
    """构造测试用EnvInfo，确保local_ip被正确传入命名空间栈。"""

    return EnvInfo(local_ip=local_ip, hostname=f"host-{local_ip}", machine_id="m")


class TestEntityNameSpace(unittest.TestCase):
    """测试EntityNameSpace类的功能"""

    def test_default_namespace(self):
        """在没有上下文时返回默认命名空间"""

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

    def test_single_context(self):
        """单个上下文管理器应覆盖并恢复命名空间"""

        env_info = make_env("10.0.0.1")

        with EntityNameSpace(env_info):
            self.assertEqual("10.0.0.1", EntityNameSpace.get_namespace())

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

    def test_nested_contexts(self):
        """嵌套上下文应按照后进先出顺序恢复"""

        env_1 = make_env("10.0.0.1")
        env_2 = make_env("10.0.0.2")
        env_3 = make_env("10.0.0.3")

        with EntityNameSpace(env_1):
            self.assertEqual("10.0.0.1", EntityNameSpace.get_namespace())

            with EntityNameSpace(env_2):
                self.assertEqual("10.0.0.2", EntityNameSpace.get_namespace())

                with EntityNameSpace(env_3):
                    self.assertEqual("10.0.0.3", EntityNameSpace.get_namespace())

                self.assertEqual("10.0.0.2", EntityNameSpace.get_namespace())

            self.assertEqual("10.0.0.1", EntityNameSpace.get_namespace())

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

    def test_multiple_contexts_same_level(self):
        """连续使用不同上下文应各自生效并恢复默认值"""

        with EntityNameSpace(make_env("192.168.0.1")):
            self.assertEqual("192.168.0.1", EntityNameSpace.get_namespace())

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

        with EntityNameSpace(make_env("192.168.0.2")):
            self.assertEqual("192.168.0.2", EntityNameSpace.get_namespace())

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

    def test_thread_isolation(self):
        """不同线程的命名空间栈互不影响"""

        results = {}
        barrier = threading.Barrier(3)

        def thread_func(thread_id: int):
            env_info = make_env(f"namespace-{thread_id}")
            barrier.wait()

            results[f"{thread_id}_before"] = EntityNameSpace.get_namespace()

            with EntityNameSpace(env_info):
                results[f"{thread_id}_inside"] = EntityNameSpace.get_namespace()
                time.sleep(0.01)
                results[f"{thread_id}_inside_after_sleep"] = (
                    EntityNameSpace.get_namespace()
                )

            results[f"{thread_id}_after"] = EntityNameSpace.get_namespace()

        threads = [threading.Thread(target=thread_func, args=(i,)) for i in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for i in range(3):
            self.assertEqual(DEFAULT_NAMESPACE, results[f"{i}_before"])
            self.assertEqual(f"namespace-{i}", results[f"{i}_inside"])
            self.assertEqual(f"namespace-{i}", results[f"{i}_inside_after_sleep"])
            self.assertEqual(DEFAULT_NAMESPACE, results[f"{i}_after"])

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

    def test_nested_contexts_in_threads(self):
        """线程内嵌套上下文应独立生效"""

        results = {}

        def thread_func():
            results["level_0"] = EntityNameSpace.get_namespace()

            with EntityNameSpace(make_env("thread-1")):
                results["level_1"] = EntityNameSpace.get_namespace()

                with EntityNameSpace(make_env("thread-2")):
                    results["level_2"] = EntityNameSpace.get_namespace()

                results["back_to_1"] = EntityNameSpace.get_namespace()

            results["back_to_0"] = EntityNameSpace.get_namespace()

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        self.assertEqual(DEFAULT_NAMESPACE, results["level_0"])
        self.assertEqual("thread-1", results["level_1"])
        self.assertEqual("thread-2", results["level_2"])
        self.assertEqual("thread-1", results["back_to_1"])
        self.assertEqual(DEFAULT_NAMESPACE, results["back_to_0"])

    def test_exception_handling(self):
        """发生异常时也应恢复默认命名空间"""

        env_info = make_env("exception-namespace")

        with self.assertRaises(ValueError):
            with EntityNameSpace(env_info):
                self.assertEqual("exception-namespace", EntityNameSpace.get_namespace())
                raise ValueError("Test exception")

        self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())

    def test_namespace_with_special_characters(self):
        """支持包含特殊字符的命名空间名称"""

        special_names = [
            "namespace-with-dashes",
            "namespace_with_underscores",
            "namespace.with.dots",
            "namespace/with/slashes",
            "命名空间中文",
            "namespace 123",
            "",
        ]

        for name in special_names:
            with EntityNameSpace(make_env(name)):
                self.assertEqual(name, EntityNameSpace.get_namespace())
            self.assertEqual(DEFAULT_NAMESPACE, EntityNameSpace.get_namespace())


if __name__ == "__main__":
    unittest.main()
