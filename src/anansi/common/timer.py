"""Synchronous wait utility for polling-based condition checks.

Provides sync_wait_until(), a polling function that repeatedly checks a
condition function until it returns True or a timeout is reached.

Usage:
    ```python
    # Wait until stop event is set (up to 5 seconds)
    success = sync_wait_until(
        lambda: stop_event.is_set(),
        timeout=5.0,
        check_interval=0.5
    )
    if success:
        print("Condition met before timeout")
    else:
        print("Timeout occurred")

    # Infinite wait
    sync_wait_until(lambda: process.running, check_interval=0.1)
    ```

Parameters:
    condition_func: Callable returning bool; True stops waiting
    timeout: Maximum wait time in seconds (None = infinite)
    check_interval: Sleep duration between checks (default: 0.1s)

Returns:
    True if condition met before timeout, False if timeout reached

Notes:
    Used by AnansiCore background loop for graceful shutdown coordination.
    Busy-waiting sleep intervals are typically 0.1-0.5 seconds.
"""

import time
from typing import Callable, Optional


def sync_wait_until(
    condition_func: Callable[[], bool],
    timeout: Optional[float] = None,
    check_interval: float = 0.1,
) -> bool:
    """Synchronously wait until a condition is met or timeout occurs."""
    start_time = time.time()
    while True:
        if condition_func():
            return True
        if timeout is not None and (time.time() - start_time) > timeout:
            return False
        time.sleep(check_interval)
