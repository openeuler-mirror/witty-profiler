"""
ProcessContextManager单元测试
测试进程上下文管理器的生命周期管理功能
"""
import multiprocessing
import os
import signal
import time
import unittest
from unittest.mock import MagicMock, Mock, patch

from anansi.common.worker_context import ProcessContextManager


# ============= 测试辅助函数 =============
def simple_worker():
    """简单的工作函数，立即返回"""
    time.sleep(0.1)


def long_running_worker():
    """长时间运行的工作函数"""
    time.sleep(10)


def worker_with_args(value, multiplier=2):
    """带参数的工作函数"""
    result = value * multiplier
    time.sleep(0.1)
    return result


def worker_with_exception():
    """会抛出异常的工作函数"""
    time.sleep(0.1)
    raise ValueError("Worker exception")


def worker_that_handles_sigterm(queue):
    """处理SIGTERM信号的工作函数"""
    def sigterm_handler(signum, frame):
        queue.put("SIGTERM_RECEIVED")
        raise KeyboardInterrupt("SIGTERM received")
    
    signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        queue.put("EXITED_GRACEFULLY")


# ============= Mock辅助类 =============
class MockProcess:
    """模拟multiprocessing.Process的行为"""
    def __init__(self, target=None, args=None, kwargs=None):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.pid = 12345
        self._is_alive = True
        self._exitcode = None
        
    def start(self):
        """模拟启动进程"""
        self._is_alive = True
        
    def is_alive(self):
        """模拟检查进程是否存活"""
        return self._is_alive
    
    def join(self, timeout=None):
        """模拟等待进程结束"""
        pass
    
    def terminate(self):
        """模拟强制终止进程"""
        self._is_alive = False


# ============= 测试用例 =============
class TestProcessContextManagerInit(unittest.TestCase):
    """测试ProcessContextManager的初始化"""
    
    def test_init_with_target_only(self):
        """测试仅提供target_func的初始化"""
        manager = ProcessContextManager(simple_worker)
        self.assertEqual(manager.target_func, simple_worker)
        self.assertEqual(manager.args, ())
        self.assertEqual(manager.kwargs, {})
        self.assertIsNone(manager.process)
        self.assertEqual(manager.timeout, 3)
    
    def test_init_with_args(self):
        """测试提供位置参数的初始化"""
        manager = ProcessContextManager(worker_with_args, 10)
        self.assertEqual(manager.args, (10,))
        
    def test_init_with_kwargs(self):
        """测试提供关键字参数的初始化"""
        manager = ProcessContextManager(worker_with_args, value=5, multiplier=3)
        self.assertEqual(manager.kwargs, {"value": 5, "multiplier": 3})
        
    def test_init_with_mixed_args(self):
        """测试同时提供位置参数和关键字参数的初始化"""
        manager = ProcessContextManager(worker_with_args, 5, multiplier=4)
        self.assertEqual(manager.args, (5,))
        self.assertEqual(manager.kwargs, {"multiplier": 4})


class TestProcessContextManagerEnter(unittest.TestCase):
    """测试ProcessContextManager的__enter__方法"""
    
    @patch('multiprocessing.Process')
    @patch('multiprocessing.get_start_method', return_value='spawn')
    def test_enter_creates_and_starts_process(self, mock_get_start_method, mock_process_class):
        """测试__enter__创建并启动进程"""
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process
        
        manager = ProcessContextManager(simple_worker)
        result = manager.__enter__()
        
        # 验证进程被创建和启动
        mock_process_class.assert_called_once_with(
            target=simple_worker, args=(), kwargs={}
        )
        mock_process.start.assert_called_once()
        self.assertEqual(result, mock_process)
        self.assertEqual(manager.process, mock_process)
    
    @patch('multiprocessing.Process')
    def test_enter_with_args_and_kwargs(self, mock_process_class):
        """测试__enter__正确传递参数"""
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process
        
        manager = ProcessContextManager(worker_with_args, 10, multiplier=2)
        manager.__enter__()
        
        mock_process_class.assert_called_once_with(
            target=worker_with_args, args=(10,), kwargs={"multiplier": 2}
        )


class TestProcessContextManagerExit(unittest.TestCase):
    """测试ProcessContextManager的__exit__方法"""
    
    def test_exit_returns_false(self):
        """测试__exit__总是返回False（不抑制异常）"""
        manager = ProcessContextManager(simple_worker)
        result = manager.__exit__(None, None, None)
        self.assertFalse(result)
    
    def test_exit_when_process_not_started(self):
        """测试进程未启动时的__exit__行为"""
        manager = ProcessContextManager(simple_worker)
        # process为None
        result = manager.__exit__(None, None, None)
        self.assertFalse(result)
    
    @patch('os.kill')
    def test_exit_when_process_already_dead(self, mock_kill):
        """测试进程已结束时的__exit__行为"""
        manager = ProcessContextManager(simple_worker)
        manager.process = MagicMock()
        manager.process.is_alive.return_value = False
        
        result = manager.__exit__(None, None, None)
        
        # 不应该尝试终止已死进程
        mock_kill.assert_not_called()
        self.assertFalse(result)
    
    @patch('os.kill')
    def test_exit_sends_sigterm_to_alive_process(self, mock_kill):
        """测试__exit__向存活进程发送SIGTERM信号"""
        manager = ProcessContextManager(simple_worker)
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.is_alive.return_value = True
        manager.process = mock_process
        
        manager.__exit__(None, None, None)
        
        # 验证发送了SIGTERM信号
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)
        mock_process.join.assert_called()
    
    @patch('os.kill', side_effect=OSError("Process not found"))
    def test_exit_handles_sigterm_failure(self, mock_kill):
        """测试__exit__处理发送SIGTERM失败的情况"""
        manager = ProcessContextManager(simple_worker)
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.is_alive.return_value = True
        manager.process = mock_process
        
        # 应该不抛出异常
        result = manager.__exit__(None, None, None)
        self.assertFalse(result)
        mock_process.join.assert_called()
    
    @patch('os.kill')
    def test_exit_terminates_if_graceful_shutdown_fails(self, mock_kill):
        """测试优雅退出失败后强制终止进程"""
        manager = ProcessContextManager(simple_worker)
        mock_process = MagicMock()
        mock_process.pid = 12345
        # 第一次调用is_alive返回True，join后仍返回True
        mock_process.is_alive.side_effect = [True, True, True]
        manager.process = mock_process
        
        manager.__exit__(None, None, None)
        
        # 验证调用了terminate
        mock_process.terminate.assert_called_once()
    
    @patch('os.kill')
    def test_exit_with_custom_timeout(self, mock_kill):
        """测试自定义超时时间"""
        manager = ProcessContextManager(simple_worker)
        manager.timeout = 5
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.is_alive.return_value = True
        manager.process = mock_process
        
        manager.__exit__(None, None, None)
        
        # 验证join使用了自定义超时
        mock_process.join.assert_any_call(timeout=5)


class TestProcessContextManagerIntegration(unittest.TestCase):
    """ProcessContextManager的集成测试"""
    
    def test_simple_worker_execution(self):
        """测试简单工作进程的完整生命周期"""
        with ProcessContextManager(simple_worker) as process:
            self.assertIsInstance(process, multiprocessing.Process)
            self.assertTrue(process.is_alive())
            process.join(timeout=2)
        
        # 退出上下文后进程应该已结束
        self.assertFalse(process.is_alive())
        self.assertEqual(process.exitcode, 0)
    
    def test_worker_with_arguments(self):
        """测试带参数的工作进程"""
        queue = multiprocessing.Queue()
        
        def worker_with_queue(q, value):
            q.put(value * 2)
        
        with ProcessContextManager(worker_with_queue, queue, 21) as process:
            process.join(timeout=2)
        
        result = queue.get(timeout=1)
        self.assertEqual(result, 42)
    
    def test_long_running_process_termination(self):
        """测试长时间运行进程的终止"""
        with ProcessContextManager(long_running_worker) as process:
            time.sleep(0.2)
            self.assertTrue(process.is_alive())
            # 退出上下文时应该被终止
        
        # 进程应该被终止
        self.assertFalse(process.is_alive())
    
    def test_process_graceful_termination_with_sigterm(self):
        """测试进程优雅处理SIGTERM信号"""
        queue = multiprocessing.Queue()
        
        with ProcessContextManager(worker_that_handles_sigterm, queue) as process:
            time.sleep(0.2)
            self.assertTrue(process.is_alive())
        
        # 验证进程收到了SIGTERM并优雅退出
        try:
            msg = queue.get(timeout=2)
            self.assertEqual(msg, "SIGTERM_RECEIVED")
            msg = queue.get(timeout=2)
            self.assertEqual(msg, "EXITED_GRACEFULLY")
        except multiprocessing.queues.Empty:
            self.fail("Process did not handle SIGTERM gracefully")
    
    def test_context_manager_does_not_suppress_exceptions(self):
        """测试上下文管理器不抑制外部异常"""
        with self.assertRaises(RuntimeError):
            with ProcessContextManager(simple_worker) as process:
                process.join(timeout=2)
                raise RuntimeError("Test exception")


class TestProcessContextManagerEdgeCases(unittest.TestCase):
    """测试ProcessContextManager的边界情况"""
    
    def test_worker_that_raises_exception(self):
        """测试工作函数抛出异常的情况"""
        with ProcessContextManager(worker_with_exception) as process:
            process.join(timeout=2)
        
        # 进程应该以非零退出码结束
        self.assertNotEqual(process.exitcode, 0)
        self.assertFalse(process.is_alive())
    
    def test_multiple_enter_exit_cycles(self):
        """测试多次使用同一个管理器实例（不推荐但应该测试）"""
        manager = ProcessContextManager(simple_worker)
        
        # 第一次使用
        process1 = manager.__enter__()
        self.assertTrue(process1.is_alive())
        process1.join(timeout=2)
        manager.__exit__(None, None, None)
        
        # 第二次使用应该创建新进程
        process2 = manager.__enter__()
        self.assertTrue(process2.is_alive())
        self.assertNotEqual(process1, process2)
        process2.join(timeout=2)
        manager.__exit__(None, None, None)
    
    def test_process_dies_before_exit(self):
        """测试进程在__exit__前自然结束"""
        with ProcessContextManager(simple_worker) as process:
            process.join(timeout=2)
            self.assertFalse(process.is_alive())
        
        # __exit__应该正常处理已结束的进程
        self.assertFalse(process.is_alive())


if __name__ == "__main__":
    unittest.main()
