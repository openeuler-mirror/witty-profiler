"""Unit tests for Anansi backend base classes and registry.

Tests the Server ABC, ServerMeta metaclass auto-registration, and
ServerFactory singleton for server instantiation and selection.

Test Coverage:
    - ServerMeta metaclass registration of concrete servers
    - ServerMeta skipping abstract base classes
    - Server ABC initialization and abstract method enforcement
    - ServerFactory singleton instance uniqueness
    - ServerFactory server creation with explicit type
    - ServerFactory server creation with auto-selection preference
    - ServerFactory fallback to first available server
    - ServerFactory error handling (missing type, no servers)
    - ServerFactory listing available servers
"""

import unittest
from unittest.mock import MagicMock, patch

from anansi.backend.base import Server, ServerFactory, ServerMeta
from anansi.common.singleton import Singleton


class MockServer(Server):
    """Concrete mock server implementation for testing."""

    def __init__(self, core):
        super().__init__(core)
        self._run_online_called_cnt = 0
        self._run_offline_called_cnt = 0

    def run_online(self, addr: str, port: int):
        """Mock online implementation."""
        self._run_online_called_cnt += 1

    def run_offline(self, duration: float):
        """Mock offline implementation."""
        self._run_offline_called_cnt += 1


class AnotherMockServer(Server):
    """Another concrete mock server for testing selection."""

    def run_online(self, addr: str, port: int):
        """Mock online implementation."""
        pass

    def run_offline(self, duration: float):
        """Mock offline implementation."""
        pass


class TestServerMeta(unittest.TestCase):
    """Test suite for ServerMeta metaclass registration."""

    def setUp(self):
        """Clear server registry before each test."""
        ServerMeta._registry.clear()

    def test_server_meta_registers_concrete_server(self):
        """Test that concrete Server subclasses auto-register in registry."""

        class ConcreteServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        registry = ServerMeta.get_registry()
        self.assertIn("ConcreteServer", registry)
        self.assertIs(registry["ConcreteServer"], ConcreteServer)

    def test_server_meta_skips_abstract_servers(self):
        """Test that abstract servers with unimplemented methods don't register."""
        from abc import abstractmethod

        class PartialAbstractServer(Server):
            @abstractmethod
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        registry = ServerMeta.get_registry()
        self.assertNotIn("PartialAbstractServer", registry)

    def test_server_meta_multiple_registrations(self):
        """Test that multiple concrete servers register independently."""

        class FirstServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        class SecondServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        registry = ServerMeta.get_registry()
        self.assertIn("FirstServer", registry)
        self.assertIn("SecondServer", registry)
        self.assertEqual(len(registry), 2)

    def test_server_meta_get_registry_returns_dict(self):
        """Test that get_registry returns the registry dictionary."""

        class TestServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        registry = ServerMeta.get_registry()
        self.assertIsInstance(registry, dict)
        self.assertIn("TestServer", registry)

    def test_server_meta_registry_contains_class_type(self):
        """Test that registry values are the actual class types."""

        class CustomServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        registry = ServerMeta.get_registry()
        registered_class = registry["CustomServer"]
        self.assertEqual(registered_class, CustomServer)
        self.assertTrue(issubclass(registered_class, Server))


class TestServer(unittest.TestCase):
    """Test suite for Server ABC."""

    def setUp(self):
        """Create mock AnansiCore for testing."""
        self.mock_core = MagicMock()

    def test_server_initialization_with_core(self):
        """Test that Server stores core reference on initialization."""
        server = MockServer(self.mock_core)
        self.assertIs(server._core, self.mock_core)

    def test_server_run_online_is_abstract(self):
        """Test that run_online must be implemented by subclasses."""

        class IncompleteServer(Server):
            def run_offline(self, duration: float):
                pass

        with self.assertRaises(TypeError):
            IncompleteServer(self.mock_core)

    def test_server_run_offline_is_abstract(self):
        """Test that run_offline must be implemented by subclasses."""

        class IncompleteServer(Server):
            def run_online(self, addr: str, port: int):
                pass

        with self.assertRaises(TypeError):
            IncompleteServer(self.mock_core)

    def test_concrete_server_can_be_instantiated(self):
        """Test that concrete Server subclasses can be instantiated."""
        server = MockServer(self.mock_core)
        self.assertIsInstance(server, Server)
        self.assertIsInstance(server, MockServer)

    def test_server_core_attribute_accessible(self):
        """Test that server core is accessible through _core attribute."""
        server = MockServer(self.mock_core)

        self.assertEqual(server._core, self.mock_core)


class TestServerFactory(unittest.TestCase):
    """Test suite for ServerFactory singleton."""

    def setUp(self):
        """Clear registry and factory before each test."""
        ServerMeta._registry.clear()
        ServerFactory.clear_singleton()
        self.mock_core = MagicMock()

    def test_server_factory_singleton_instance(self):
        """Test that ServerFactory returns same instance on multiple calls."""
        factory1 = ServerFactory.get_instance()
        factory2 = ServerFactory.get_instance()
        self.assertIs(factory1, factory2)

    def test_server_factory_create_server_with_explicit_type(self):
        """Test creating server with explicit server_type parameter."""

        class ExplicitServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server = factory.create_server(
            server_type="ExplicitServer", core=self.mock_core
        )

        self.assertIsNotNone(server)
        self.assertIsInstance(server, ExplicitServer)
        self.assertIs(server._core, self.mock_core)

    def test_server_factory_create_server_prefers_fastapi(self):
        """Test that factory prefers FastAPIServer if available."""

        class OnlineDisabledServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        class FastAPIServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server = factory.create_server(core=self.mock_core)

        self.assertIsNotNone(server)
        self.assertIsInstance(server, FastAPIServer)

    def test_server_factory_fallback_to_first_available(self):
        """Test that factory falls back to first available when FastAPI missing."""

        class OnlyServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server = factory.create_server(core=self.mock_core)

        self.assertIsNotNone(server)
        self.assertIsInstance(server, OnlyServer)

    def test_server_factory_returns_none_when_no_servers_available(self):
        """Test that factory returns None when registry is empty."""
        factory = ServerFactory.get_instance()
        server = factory.create_server(core=self.mock_core)

        self.assertIsNone(server)

    def test_server_factory_returns_none_for_missing_type(self):
        """Test that factory returns None for non-existent server type."""

        class AvailableServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server = factory.create_server(
            server_type="NonExistentServer", core=self.mock_core
        )

        self.assertIsNone(server)

    def test_server_factory_uses_default_core_when_none_provided(self):
        """Test that factory uses AnansiCore default when core is None."""

        class DefaultCoreServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()

        with patch("anansi.controller.anansi_core.AnansiCore") as mock_anansi_core:
            mock_instance = MagicMock()
            mock_anansi_core.get_instance.return_value = mock_instance

            server = factory.create_server(core=None)

            self.assertIsNotNone(server)
            self.assertIsInstance(server, DefaultCoreServer)
            mock_anansi_core.get_instance.assert_called_once()

    def test_server_factory_list_available_servers_empty(self):
        """Test listing servers when registry is empty."""
        factory = ServerFactory.get_instance()
        servers = factory.list_available_servers()

        self.assertIsInstance(servers, list)
        self.assertEqual(len(servers), 0)

    def test_server_factory_list_available_servers(self):
        """Test listing all registered servers."""

        class FirstServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        class SecondServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        servers = factory.list_available_servers()

        self.assertIsInstance(servers, list)
        self.assertEqual(len(servers), 2)
        self.assertIn("FirstServer", servers)
        self.assertIn("SecondServer", servers)

    def test_server_factory_list_contains_created_server_types(self):
        """Test that list_available_servers includes all registered types."""

        class ListableServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        available = factory.list_available_servers()
        registry = ServerMeta.get_registry()

        self.assertEqual(set(available), set(registry.keys()))

    def test_server_factory_multiple_creations_independent_instances(self):
        """Test that factory creates independent instances for each call."""

        class IndependentServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server1 = factory.create_server(
            server_type="IndependentServer", core=self.mock_core
        )
        server2 = factory.create_server(
            server_type="IndependentServer", core=self.mock_core
        )

        self.assertIsNot(server1, server2)
        self.assertIsInstance(server1, IndependentServer)
        self.assertIsInstance(server2, IndependentServer)


class TestServerFactoryIntegration(unittest.TestCase):
    """Integration tests for ServerFactory with multiple servers."""

    def setUp(self):
        """Clear registry and factory before each test."""
        ServerMeta._registry.clear()
        ServerFactory.clear_singleton()
        self.mock_core = MagicMock()

    def test_fastapi_server_preference_over_fallback(self):
        """Test that FastAPIServer is chosen over other available servers."""

        class OnlineDisabledServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        class FastAPIServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server = factory.create_server(core=self.mock_core)

        self.assertIsInstance(server, FastAPIServer)
        self.assertNotIsInstance(server, OnlineDisabledServer)

    def test_explicit_type_overrides_preference(self):
        """Test that explicit server_type overrides FastAPI preference."""

        class OnlineDisabledServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        class FastAPIServer(Server):
            def run_online(self, addr: str, port: int):
                pass

            def run_offline(self, duration: float):
                pass

        factory = ServerFactory.get_instance()
        server = factory.create_server(
            server_type="OnlineDisabledServer", core=self.mock_core
        )

        self.assertIsInstance(server, OnlineDisabledServer)
        self.assertNotIsInstance(server, FastAPIServer)

    def test_workflow_register_create_use(self):
        """Test complete workflow: register server, create instance, use it."""

        class WorkflowServer(Server):
            call_count = 0

            def run_online(self, addr: str, port: int):
                self.call_count += 1

            def run_offline(self, duration: float):
                self.call_count += 1

        factory = ServerFactory.get_instance()
        available = factory.list_available_servers()
        self.assertIn("WorkflowServer", available)

        server = factory.create_server(
            server_type="WorkflowServer", core=self.mock_core
        )
        self.assertIsNotNone(server)

        server.run_online("127.0.0.1", 18090)
        self.assertEqual(server.call_count, 1)


if __name__ == "__main__":
    unittest.main()
