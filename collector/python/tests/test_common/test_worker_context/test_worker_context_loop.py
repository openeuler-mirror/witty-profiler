import logging
import multiprocessing
import queue
import signal
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from witty_profiler.common.logging import get_logger
from witty_profiler.common.worker_context import ProcessContextManager

LOGGER = get_logger(__name__)


def task_look_with_keyboard_interrupt(result_queue):
    import signal

    signal.signal(signal.SIGTERM, signal.default_int_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 向 parent 报告进了 KeyboardInterrupt
        LOGGER.info("Child process received KeyboardInterrupt")
        result_queue.put("keyboard_interrupt")


class TestProcessContextManager(unittest.TestCase):

    def test_sigterm_triggers_keyboard_interrupt(self):
        q = multiprocessing.Queue()

        with ProcessContextManager(task_look_with_keyboard_interrupt, q) as process:
            time.sleep(0.2)

        # ContextManager 退出后，子进程应该已经报告
        try:
            msg = q.get(timeout=2)
        except queue.Empty:
            self.fail("Child never received KeyboardInterrupt")

        self.assertEqual(msg, "keyboard_interrupt")


if __name__ == "__main__":
    case = TestProcessContextManager()
    case.test_sigterm_triggers_keyboard_interrupt()
