"""Unit tests for EnvManager using unittest.TestCase and mocks.

This suite verifies the observable behaviors of EnvManager without relying on
real network or filesystem access. Each test is atomic and focuses on a single
scenario, following the project's unittest guidelines.
"""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from anansi.common.env_manager import EnvManager


class DummySocket:
    """A minimal socket replacement for local IP detection tests."""

    def __init__(self, ip: str = "127.0.0.1"):
        self._ip = ip

    def connect(self, addr):
        # The real implementation doesn't actually send data; we just accept calls.
        return None

    def getsockname(self):
        return (self._ip, 0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestEnvManager(unittest.TestCase):
    def setUp(self):
        # Ensure fresh singleton for each test
        EnvManager.clear_singleton()
        self.mgr: EnvManager = EnvManager()

    def tearDown(self):
        EnvManager.clear_singleton()

    def test_get_local_ip_success_caches_and_refreshes(self):
        calls = {"count": 0}

        def fake_socket(*args, **kwargs):
            calls["count"] += 1
            return DummySocket(ip="10.0.0.5")

        with patch("socket.socket", new=fake_socket):
            ip1 = self.mgr.get_local_ip(refresh=True)
            self.assertEqual(ip1, "10.0.0.5")
            self.assertEqual(calls["count"], 1)

            # Cached path (no refresh): should not call socket again
            ip2 = self.mgr.get_local_ip(refresh=False)
            self.assertEqual(ip2, "10.0.0.5")
            self.assertEqual(calls["count"], 1)

            # Refresh forces re-detection
            ip3 = self.mgr.get_local_ip(refresh=True)
            self.assertEqual(ip3, "10.0.0.5")
            self.assertEqual(calls["count"], 2)

    def test_get_local_ip_exception_returns_none(self):
        def raising_socket(*args, **kwargs):
            raise OSError("network not available")

        with patch("socket.socket", new=raising_socket):
            ip = self.mgr.get_local_ip(refresh=True)
            self.assertIsNone(ip)

    def test_msgspec_compatible_true_sets_cache(self):
        # Use real msgspec if available; skip otherwise to avoid brittle fakes.
        try:
            import msgspec  # noqa: F401
        except Exception:
            self.skipTest("msgspec not available in environment")

        self.assertTrue(self.mgr.msgspec_compatible(refresh=True))
        # Cached result remains True without re-evaluation
        self.assertTrue(self.mgr.msgspec_compatible(refresh=False))

    def test_msgspec_compatible_false_sets_cache_false(self):
        class _Struct:
            pass

        class _MsgpackNS:
            @staticmethod
            def encode(obj):
                return b"dummy"

            @staticmethod
            def decode(data, type):
                # Wrong value forces False
                return type(41)

        fake_msgspec = SimpleNamespace(Struct=_Struct, msgpack=_MsgpackNS())

        with patch.dict(sys.modules, {"msgspec": fake_msgspec}):
            self.assertFalse(self.mgr.msgspec_compatible(refresh=True))

    def test_get_hostname_returns_cached_value(self):
        with patch("socket.gethostname", return_value="myhost"):
            # First detection
            self.assertEqual(self.mgr.get_hostname(refresh=True), "myhost")

        # Cached path should return same and not call socket again
        with patch(
            "socket.gethostname",
            side_effect=AssertionError("should not be called"),
        ):
            self.assertEqual(self.mgr.get_hostname(refresh=False), "myhost")

    def test_get_machine_id_success_reads_and_caches(self):
        # Simulate reading /etc/machine-id
        m = mock_open(read_data="abc123\n")
        with patch("builtins.open", m):
            self.assertEqual(self.mgr.get_machine_id(refresh=True), "abc123")

        # Cached path
        with patch(
            "builtins.open",
            side_effect=AssertionError("should not be called"),
        ):
            self.assertEqual(self.mgr.get_machine_id(refresh=False), "abc123")

    def test_get_machine_id_fallback_generates_random_id(self):
        with patch("builtins.open", side_effect=FileNotFoundError()):
            mid = self.mgr.get_machine_id(refresh=True)
        self.assertTrue(mid.startswith("unknown_random_"))
        suffix = mid.split("unknown_random_")[-1]
        # Should be 8 hex chars
        self.assertEqual(len(suffix), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in suffix))


if __name__ == "__main__":
    unittest.main()
