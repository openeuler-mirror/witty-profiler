import unittest
from unittest.mock import patch

from anansi.common.id_manager import GlobalIDManager, IdObject


class NotImplementedIdObject(IdObject):
    def __init__(self, gid: str):
        self._global_id = gid


class ConcreteIdObject(NotImplementedIdObject):

    @property
    def global_id(self) -> str:
        return self._global_id


class TestGlobalIDManager(unittest.TestCase):

    def setUp(self):
        # 每次测试前重置单例和内部状态
        GlobalIDManager._instance = None
        if hasattr(GlobalIDManager, "_global_id_map"):
            GlobalIDManager._global_id_map.clear()

    def test_singleton_pattern(self):
        """测试 GlobalIDManager 是单例"""
        mgr1 = GlobalIDManager.get_instance()
        mgr2 = GlobalIDManager.get_instance()
        self.assertIs(mgr1, mgr2)

    def test_abstract_method(self):
        """测试 IdObject 的抽象方法"""
        with self.assertRaises(NotImplementedError) as cm:
            obj = NotImplementedIdObject("id1")
            a = obj.global_id

    def test_record_and_exists(self):
        """测试 record 和 exists 方法"""
        mgr = GlobalIDManager.get_instance()
        obj = ConcreteIdObject("id1")

        self.assertFalse(mgr.exists("id1"))
        mgr.record("id1", obj)
        self.assertTrue(mgr.exists("id1"))

        # 重复记录应抛出异常
        with self.assertRaises(RuntimeError) as cm:
            mgr.record("id1", obj)
        self.assertIn("already exists", str(cm.exception))

    def test_lookup_by_global_id(self):
        """测试 lookup_by_global_id"""
        mgr = GlobalIDManager.get_instance()
        obj1 = ConcreteIdObject("id1")
        obj2 = ConcreteIdObject("id2")

        mgr.record("id1", obj1)
        mgr.record("id2", obj2)

        self.assertIs(mgr.lookup_by_global_id("id1"), obj1)
        self.assertIs(mgr.lookup_by_global_id("id2"), obj2)
        self.assertIsNone(mgr.lookup_by_global_id("nonexistent"))
        self.assertEqual(mgr.lookup_by_global_id("nonexistent", "default"), "default")

    def test_release_global_id(self):
        """测试 release_global_id"""
        mgr = GlobalIDManager.get_instance()
        obj = ConcreteIdObject("id1")
        mgr.record("id1", obj)

        self.assertTrue(mgr.exists("id1"))
        mgr.release_global_id("id1")
        self.assertFalse(mgr.exists("id1"))

        # 释放不存在的 ID 不应报错
        mgr.release_global_id("nonexistent")

    def test_update_id(self):
        """测试 update_id"""
        mgr = GlobalIDManager.get_instance()
        obj = ConcreteIdObject("old_id")
        mgr.record("old_id", obj)

        # 正常更新
        mgr.update_id(obj, "new_id")
        self.assertFalse(mgr.exists("old_id"))
        self.assertTrue(mgr.exists("new_id"))
        self.assertIs(mgr.lookup_by_global_id("new_id"), obj)

        # 更新到已存在的 ID 应失败
        obj2 = ConcreteIdObject("conflict_id")
        mgr.record("conflict_id", obj2)
        with self.assertRaises(RuntimeError) as cm:
            mgr.update_id(obj, "conflict_id")
        self.assertIn("already exists", str(cm.exception))

        # 更新未注册的对象应失败
        unregistered_obj = ConcreteIdObject("unreg")
        with self.assertRaises(RuntimeError) as cm:
            mgr.update_id(unregistered_obj, "any_id")
        self.assertIn("Object not found", str(cm.exception))

    def test_create_ensure_unique_id_new(self):
        """测试 create_ensure_unique_id 创建新对象"""
        obj1 = ConcreteIdObject.create_ensure_unique_id("gid1")
        self.assertIsInstance(obj1, ConcreteIdObject)
        self.assertEqual(obj1.global_id, "gid1")

        # 再次创建相同 global_id 应返回同一个实例
        obj2 = ConcreteIdObject.create_ensure_unique_id("gid1")
        self.assertIs(obj1, obj2)

    def test_create_ensure_unique_id_with_none_global_id(self):
        """测试 global_id 为 None 时抛出异常"""

        class BadIdObject(IdObject):
            @property
            def global_id(self) -> str:
                return None  # type: ignore

        with self.assertRaises(RuntimeError) as cm:
            BadIdObject.create_ensure_unique_id()
        self.assertIn("Global ID cannot be None", str(cm.exception))

    def test_lt_comparison(self):
        """测试 IdObject 的 __lt__ 方法"""
        obj1 = ConcreteIdObject("a")
        obj2 = ConcreteIdObject("b")
        self.assertTrue(obj1 < obj2)
        self.assertFalse(obj2 < obj1)


if __name__ == "__main__":
    unittest.main()
