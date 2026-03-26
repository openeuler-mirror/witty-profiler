"""Unit tests for AnansiServer controller singleton.

Tests the AnansiServer controller's initialization, backend selection,
and delegation to appropriate server implementations.

Test Coverage:
    - Singleton initialization and configuration loading
    - Backend selection based on preferred_backend config
    - Delegation to backend for run_online/run_offline
    - Handling missing/invalid backend configuration
    - Config defaults and override behavior
    - Thread-safe singleton access

Notes:
    Tests focus on AnansiServer's orchestration logic, not backend
    implementation details (covered in test_backend/).
"""

import importlib
import unittest
from unittest.mock import Mock, patch

from anansi.backend.base import Server, ServerFactory, ServerMeta
from anansi.config_manager.configs import ServerConfig


class MockServer(Server):
    """Mock server for testing AnansiServer behavior."""

    def __init__(self, core):
        super().__init__(core)
        self.run_online_called = False
        self.run_offline_called = False
        self.online_addr = None
        self.online_port = None
        self.offline_duration = None

    def run_online(self, addr: str, port: int):
        """Track run_online invocation."""
        self.run_online_called = True
        self.online_addr = addr
        self.online_port = port

    def run_offline(self, duration: float):
        """Track run_offline invocation."""
        self.run_offline_called = True
        self.offline_duration = duration


class TestAnansiServer(unittest.TestCase):
    """Test AnansiServer controller singleton behavior."""

    def setUp(self):
        """Reset singletons and mocks before each test."""
        # Store original registry for restoration
        self._original_registry = ServerMeta._registry.copy()
        importlib.import_module("anansi.backend.anansi")

    def tearDown(self):
        """Cleanup after each test."""
        # Restore original registry
        ServerMeta._registry = self._original_registry

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_initialization_with_default_config(
        self, mock_factory_class, mock_core_class, mock_config_class
    ):
        """测试使用默认配置初始化AnansiServer。

        验证：
        - 从GlobalConfigManager加载server_config
        - 使用配置的preferred_backend创建backend
        - 正确初始化AnansiCore实例
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration
        mock_config = Mock()
        mock_config.server_config = ServerConfig(
            server_addr={"host": "0.0.0.0", "port": 18090}, preferred_backend=None
        )
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory and backend
        mock_backend = MockServer(mock_core)
        mock_factory = Mock()
        mock_factory.create_server.return_value = mock_backend
        mock_factory_class.return_value = mock_factory

        # Initialize AnansiServer
        server = AnansiServer()

        # Verify core and config were loaded
        mock_core_class.get_instance.assert_called_once()
        mock_config_class.assert_called_once()
        mock_config_mgr.get_config.assert_called_once()

        # Verify factory was used to create backend
        mock_factory_class.assert_called_once()
        mock_factory.create_server.assert_called_once()

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_initialization_with_preferred_backend(
        self, mock_factory_class, mock_core_class, mock_config_class
    ):
        """测试使用指定preferred_backend初始化。

        验证：
        - 使用配置中指定的backend类型
        - 正确传递core实例给backend
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration with preferred backend
        mock_config = Mock()
        mock_config.server_config = ServerConfig(
            server_addr={"host": "localhost", "port": 9000},
            preferred_backend="MockServer",
        )
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory and backend
        mock_backend = MockServer(mock_core)
        mock_factory = Mock()
        mock_factory.create_server.return_value = mock_backend
        mock_factory_class.return_value = mock_factory

        # Initialize AnansiServer
        server = AnansiServer()

        # Verify factory was called with preferred backend
        mock_factory.create_server.assert_called_once_with(
            server_type="MockServer", core=mock_core
        )

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_initialization_fails_with_no_backend(
        self, mock_factory_class, mock_core_class, mock_config_class
    ):
        """测试当没有可用backend时初始化失败。

        验证：
        - 当factory返回None时抛出RuntimeError
        - 提供清晰的错误信息
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration
        mock_config = Mock()
        mock_config.server_config = ServerConfig()
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory returning None (no backend available)
        mock_factory = Mock()
        mock_factory.create_server.return_value = None
        mock_factory_class.return_value = mock_factory

        # Should raise RuntimeError
        with self.assertRaises(RuntimeError) as context:
            AnansiServer()

        self.assertIn("No server backend available", str(context.exception))

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_run_online_with_default_config(
        self, mock_factory_class, mock_core_class, mock_config_class
    ):
        """测试使用配置文件默认地址和端口启动在线服务。

        验证：
        - 使用config中的host和port
        - 正确调用backend的run_online方法
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration
        mock_config = Mock()
        mock_config.server_config = ServerConfig(
            server_addr={"host": "192.168.1.100", "port": 7000}, preferred_backend=None
        )
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory and backend
        mock_backend = MockServer(mock_core)
        mock_factory = Mock()
        mock_factory.create_server.return_value = mock_backend
        mock_factory_class.return_value = mock_factory

        # Initialize and run server
        server = AnansiServer()
        server.run_online()

        # Verify backend was called with config defaults
        self.assertTrue(mock_backend.run_online_called)
        self.assertEqual(mock_backend.online_addr, "192.168.1.100")
        self.assertEqual(mock_backend.online_port, 7000)

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_run_online_with_override_params(
        self, mock_factory_class, mock_core_class, mock_config_class
    ):
        """测试使用参数覆盖配置启动在线服务。

        验证：
        - 优先使用传入的addr和port参数
        - 忽略配置文件中的默认值
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration
        mock_config = Mock()
        mock_config.server_config = ServerConfig(
            server_addr={"host": "0.0.0.0", "port": 18090}, preferred_backend=None
        )
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory and backend
        mock_backend = MockServer(mock_core)
        mock_factory = Mock()
        mock_factory.create_server.return_value = mock_backend
        mock_factory_class.return_value = mock_factory

        # Initialize and run server with overrides
        server = AnansiServer()
        server.run_online(addr="10.0.0.1", port=3000)

        # Verify backend was called with override params
        self.assertTrue(mock_backend.run_online_called)
        self.assertEqual(mock_backend.online_addr, "10.0.0.1")
        self.assertEqual(mock_backend.online_port, 3000)

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_run_offline(self, mock_factory_class, mock_core_class, mock_config_class):
        """测试运行离线模式。

        验证：
        - 正确调用backend的run_offline方法
        - 传递正确的duration参数
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration
        mock_config = Mock()
        mock_config.server_config = ServerConfig()
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory and backend
        mock_backend = MockServer(mock_core)
        mock_factory = Mock()
        mock_factory.create_server.return_value = mock_backend
        mock_factory_class.return_value = mock_factory

        # Initialize and run offline
        server = AnansiServer()
        test_duration = 30.5
        server.run_offline(duration=test_duration)

        # Verify backend was called with correct duration
        self.assertTrue(mock_backend.run_offline_called)
        self.assertEqual(mock_backend.offline_duration, test_duration)

    @patch("anansi.backend.anansi.GlobalConfigManager")
    @patch("anansi.backend.anansi.AnansiCore")
    @patch("anansi.backend.anansi.ServerFactory")
    def test_singleton_behavior(
        self, mock_factory_class, mock_core_class, mock_config_class
    ):
        """测试AnansiServer的单例行为。

        验证：
        - 确保唯一实例
        - 配置只加载一次
        """
        # Import here to use fresh mocks
        from anansi.backend.anansi import AnansiServer

        # Clear singleton for clean test
        AnansiServer.clear_singleton()

        # Mock configuration
        mock_config = Mock()
        mock_config.server_config = ServerConfig()
        mock_config_mgr = Mock()
        mock_config_mgr.get_config.return_value = mock_config
        mock_config_class.return_value = mock_config_mgr

        # Mock AnansiCore
        mock_core = Mock()
        mock_core_class.get_instance.return_value = mock_core

        # Mock ServerFactory and backend
        mock_backend = MockServer(mock_core)
        mock_factory = Mock()
        mock_factory.create_server.return_value = mock_backend
        mock_factory_class.return_value = mock_factory

        # Get instance multiple times
        server1 = AnansiServer.get_instance()
        server2 = AnansiServer.get_instance()

        # Verify same instance
        self.assertIs(server1, server2)

        # Config should only be constructed once
        self.assertEqual(mock_config_class.call_count, 1)


if __name__ == "__main__":
    unittest.main()
