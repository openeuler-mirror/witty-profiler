import multiprocessing as mp

from anansi.common.logging import get_logger

LOGGER = get_logger(__name__)


def pytest_configure():
    LOGGER.info("Pytest configuration")
    if mp.get_start_method(allow_none=True) is None:
        mp.set_start_method("fork")
