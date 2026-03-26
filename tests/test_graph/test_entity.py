import unittest
from abc import abstractmethod

from anansi.common.id_manager import GlobalIDManager
from anansi.entity.entity_base import Entity, EntityFactory, EntityMeta
from anansi.entity.node_entity import ProcessEntity, SharedMemoryEntity


class TestEntity(unittest.TestCase):
    def setUp(self):
        GlobalIDManager().clear_singleton()
        self.manager = GlobalIDManager.get_instance()

    def test_entity_factory(self):
        entity_factory: EntityFactory = EntityFactory.get_instance()
        e1 = entity_factory.create_entity({"entity_type": "ProcessEntity", "pid": 1})
        e2 = entity_factory.create_entity(
            {
                "entity_type": "SharedMemoryEntity",
                "shm_name": "shared",
                "shm_size": 1024,
            }
        )
        e3 = entity_factory.create_entity({"entity_type": "ProcessEntity", "pid": 1})
        e4 = entity_factory.create_entity(
            {
                "entity_type": "SharedMemoryEntity",
                "shm_name": "shared",
                "shm_size": 1024,
            },
            ensure_unique=False,
        )
        e5 = entity_factory.create_entity(e4.model_dump())
        self.assertIs(e1, e3)
        self.assertEqual(e1, e3)
        self.assertIsNot(e1, e2)
        self.assertIsNot(e2, e4)
        self.assertTrue(e2 == e4)
        self.assertIs(e2, e5)
        e6 = SharedMemoryEntity(**e4.model_dump())
        e7 = ProcessEntity()
        e8 = ProcessEntity()
        self.assertNotEqual(e7, e8)
        self.assertNotEqual(e6, e8)
        self.assertEqual(e7.pid, e8.pid + 1)

    def test_factory_create_entity_invalid(self):
        entity_factory = EntityFactory.get_instance()
        with self.assertRaises(ValueError) as cm:
            entity_factory.create_entity(
                {
                    "shm_name": "shared",
                    "shm_size": 1024,
                },
                ensure_unique=True,
            )
        self.assertIn("entity_type is required", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            entity_factory.create_entity(
                {
                    "entity_type": "NonExistentEntity",
                },
                ensure_unique=True,
            )
        self.assertIn(
            "Entity subclass 'NonExistentEntity' not found.", str(cm.exception)
        )

    def test_entity_update_gid(self):
        entity_factory = EntityFactory.get_instance()
        e1: ProcessEntity = entity_factory.create_entity(
            {
                "entity_type": "ProcessEntity",
                "pid": 1,
                "ppid": 0,
                "name": "init",
                "cmdline": "/sbin/init",
            }
        )
        old_gid = e1.global_id
        e1.pid = 2
        e3 = entity_factory.create_entity(
            {
                "entity_type": "ProcessEntity",
                "pid": 2,
                "ppid": 0,
                "name": "init",
                "cmdline": "/sbin/init",
            }
        )
        self.assertEqual(e1, e3)
        self.assertFalse(
            old_gid == e1.global_id, "old: {} new: {}".format(old_gid, e1.global_id)
        )
        self.assertFalse(self.manager.exists(old_gid))


if __name__ == "__main__":
    testcase = TestEntity()
    testcase.setUp()
    testcase.test_entity_update_gid()
    unittest.main()
