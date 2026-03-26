import multiprocessing
import signal
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from multiprocessing import Process, Queue, resource_tracker, set_start_method
from multiprocessing.shared_memory import SharedMemory

from anansi.common.worker_context import ProcessContextManager


def simple_task():
    """简单的任务函数，用于测试"""
    time.sleep(0.5)
    print("Task completed")


def long_running_task():
    """长时间运行的任务函数，用于测试终止功能"""
    time.sleep(5)  # 故意设置一个长睡眠时间来测试终止


def task_with_args(name, age):
    """带参数的任务函数"""
    time.sleep(0.1)
    print(f"Name: {name}, Age: {age}")


def task_that_raises_exception():
    """会抛出异常的任务函数"""
    time.sleep(0.1)
    raise ValueError("Test exception in process")


def task_look_with_keyboard_interrupt():
    signal.signal(signal.SIGINT, signal.default_int_handler)
    """任务会等待键盘中断"""
    while True:
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("KeyboardInterrupt caught, exiting task")
            break


class TestProcessContextManager(unittest.TestCase):

    def test_simple_task_execution_with_shm(self):
        """测试简单任务的执行"""
        with ProcessContextManager(simple_task) as process:
            shm = SharedMemory(name="test_shm", size=1024, create=True)
            shm.close()
            shm.unlink()
            process.join()  # 等待进程完成
            # 验证进程已结束
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)

    def test_simple_task_execution(self):
        """测试简单任务的执行"""
        with ProcessContextManager(simple_task) as process:
            process.join()  # 等待进程完成
            # 验证进程已结束
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)

    def test_long_running_task_termination(self):
        """测试长时间运行任务的终止"""
        with ProcessContextManager(long_running_task) as process:
            # 不等待进程自然结束，而是让它被上下文管理器终止
            # 上下文退出时会终止进程
            pass

        # 验证进程已被终止
        self.assertFalse(process.is_alive())

    def test_task_with_arguments(self):
        """测试带参数的任务"""
        with ProcessContextManager(task_with_args, "Alice", 25) as process:
            process.join()
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)

    def test_process_returned_by_enter(self):
        """测试__enter__方法返回进程对象"""
        with ProcessContextManager(simple_task) as process:
            self.assertIsInstance(process, multiprocessing.Process)
            self.assertTrue(process.is_alive())
            process.join()

    def test_exit_returns_false(self):
        """测试__exit__方法返回False（不抑制异常）"""
        # 创建一个实例来测试__exit__的行为
        manager = ProcessContextManager(simple_task)
        result = manager.__exit__(None, None, None)
        self.assertFalse(result)  # __exit__应该返回False

    def test_process_cleanup_when_alive(self):
        """测试当进程仍在运行时的清理操作"""
        with ProcessContextManager(long_running_task) as process:
            # 确保进程正在运行
            time.sleep(0.1)
            self.assertTrue(process.is_alive())

        # 退出上下文后，进程应被终止
        self.assertFalse(process.is_alive())

    def test_process_not_started_if_already_dead(self):
        """测试进程在上下文中死亡的情况"""
        with ProcessContextManager(simple_task) as process:
            process.join()  # 等待进程自然结束
            self.assertFalse(process.is_alive())

    def test_exception_propagation(self):
        """测试异常传播（__exit__不抑制异常）"""
        # 这里我们测试异常传播机制
        manager = ProcessContextManager(task_that_raises_exception)
        process = manager.__enter__()
        try:
            process.join()
        finally:
            # __exit__返回False，所以异常不会被抑制
            result = manager.__exit__(None, None, None)
            self.assertFalse(result)

    def test_kwargs_handling(self):
        """测试关键字参数处理"""

        def task_with_kwargs(name="default", age=0):
            time.sleep(0.1)
            print(f"Name: {name}, Age: {age}")

        with ProcessContextManager(task_with_kwargs, name="Bob", age=30) as process:
            process.join()
            self.assertEqual(process.exitcode, 0)

    def test_no_args_function(self):
        """测试无参数函数"""

        def no_arg_func():
            time.sleep(0.1)
            print("No args function executed")

        with ProcessContextManager(no_arg_func) as process:
            process.join()
            self.assertEqual(process.exitcode, 0)

    def test_terminate_process(self):
        """测试终止进程"""

        with ProcessContextManager(task_look_with_keyboard_interrupt) as process:
            # 确保进程正在运行
            time.sleep(0.1)
            self.assertTrue(process.is_alive())


if __name__ == "__main__":
    # """
    # 运行测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestProcessContextManager)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试结果摘要
    print(f"\nTests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("Success!" if result.wasSuccessful() else "Some tests failed.")
    print(f"Errors: {len(result.errors)}")
    print("Success!" if result.wasSuccessful() else "Some tests failed.")
    # """
