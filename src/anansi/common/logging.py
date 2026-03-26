"""Logging configuration and management utilities.

Provides centralized logging setup for Anansi framework with custom
log levels, file-based and stream-based handlers, and a singleton
LogManager for managing multiple loggers.

Key Components:
    - LoggingConfig: Dataclass for logging configuration (level, format, date format)
    - CustomLogger: Custom logger class supporting VERBOSE log level
    - LogManager: Singleton managing multiple named loggers
    - get_logger(): Convenience function to get loggers from LogManager

Custom Log Levels:
    - VERBOSE (5): Below DEBUG level, for detailed tracing
    - REPORT (25): Between INFO and WARNING, for important runtime reports

LoggingConfig Fields:
    - level: Default log level (NOTSET, DEBUG, INFO, WARNING, ERROR, etc.)
    - log_format: Format string for log messages
    - datefmt: Date/time format in log entries

LogManager Features:
    - Singleton pattern; multiple get_logger() calls return same instance
    - Caches loggers by name to avoid recreation
    - Supports file handlers (log_file_path) and stream handlers
    - Configurable propagation to parent loggers
    - Initialization from LoggingConfig, dict, or JSON file

Usage:
    ```python
    # Get default logger
    logger = get_logger(__name__)
    logger.info("Starting topology collection")
    logger.verbose("Detailed debug information")

    # Configure custom logger
    config = LoggingConfig(level="DEBUG")
    log_manager = LogManager(config)
    file_logger = log_manager.get_logger(
        name="file_logger",
        log_file_path="/tmp/anansi.log"
    )

    # Initialize from JSON
    log_manager = LogManager("/etc/anansi/logging.json")
    ```

Notes:
    Root logger (name=None) is initialized automatically on first use.
    VERBOSE level is below DEBUG and used for high-verbosity output.
    REPORT level is between INFO and WARNING for important runtime reports.
"""

import json
import logging
import os
from dataclasses import dataclass
from logging import CRITICAL, DEBUG, ERROR, INFO, NOTSET, WARNING

DEFAULT_LOG_LEVEL = "REPORT"


@dataclass
class LoggingConfig:
    """Configuration for logging setup."""

    level: str = "NOTSET"
    log_format: str = "%(asctime)s[%(levelname)s](%(filename)s:%(lineno)d) %(message)s"
    datefmt: str = "%Y-%m-%d %H:%M:%S"


VERBOSE = 5
REPORT = 25
logging.addLevelName(VERBOSE, "VERBOSE")
logging.addLevelName(REPORT, "REPORT")


class CustomLogger(logging.Logger):
    """A custom logger class that supports logging to a file."""

    def verbose(self, msg, *args, **kwargs):
        """Log 'msg % args' with severity 'VERBOSE'."""
        if self.isEnabledFor(VERBOSE):  # Custom log level
            self._log(VERBOSE, msg, args, **kwargs)

    def report(self, msg, *args, **kwargs):
        """Log 'msg % args' with severity 'REPORT'."""
        if self.isEnabledFor(REPORT):  # Custom log level
            self._log(REPORT, msg, args, **kwargs)


logging.setLoggerClass(CustomLogger)


class LogManager:
    """A simple singleton LogManager to manage multiple loggers.
    It can create and retrieve loggers with specified configurations.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LogManager, cls).__new__(cls)
            cls.__init__(cls._instance, *args, **kwargs)
        return cls._instance

    def __init__(self, logger_config: LoggingConfig | dict | str | None = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.logger_map = {}
        if isinstance(logger_config, LoggingConfig):
            pass
        elif isinstance(logger_config, dict):
            logger_config = LoggingConfig(**logger_config)
        elif isinstance(logger_config, str):
            with open(logger_config, "r", encoding="utf-8") as f:
                logger_config = json.load(f)
            logger_config = LoggingConfig(**logger_config)
        elif logger_config is None:
            logger_config = LoggingConfig()
        else:
            raise NotImplementedError(
                f"Unsupported logger_config type: {logger_config}"
            )
        self.default_logger_config: LoggingConfig = logger_config
        self._init_root_logger()

    def _init_root_logger(self):
        """Initialize the root logger."""
        root_logger_level = os.environ.get(
            "ANANSI_ROOT_LOGGER_LEVEL", DEFAULT_LOG_LEVEL
        )
        try:

            root_logger_level = logging._nameToLevel.get(
                root_logger_level.upper(), REPORT
            )
        except AttributeError as e:
            root_logger_level = REPORT
            print(
                "Invalid env variable $ANANSI_ROOT_LOGGER_LEVEL: {}, using REPORT instead. {}".format(
                    root_logger_level,
                    e,
                )
            )
        root_logger: logging.Logger = self.get_logger(
            name=None, level=root_logger_level, propagate=False
        )  # 初始化根日志器
        root_logger.log(
            level=root_logger_level,
            msg="Root logger initialized with level: %s (Default ENV at %s)"
            % (logging.getLevelName(root_logger_level), "ANANSI_ROOT_LOGGER_LEVEL"),
        )

    def get_logger(
        self,
        name: str,
        level: str = None,
        log_file_path: str = None,
        propagate: bool = None,
    ) -> logging.Logger:
        """Get a logger with specified name, level, log_file_path and propagate."""

        if not self.logger_map.get(name):
            self.logger_map[name] = self._create_new_logger(
                name, level, log_file_path, propagate
            )
        return self.logger_map[name]

    def _create_new_logger(
        self,
        name: str,
        level: str = None,
        log_file_path: str = None,
        propagate: bool = None,
    ) -> logging.Logger:
        if propagate is None:
            propagate = True
        logger = logging.getLogger(name)
        if level is None:
            level = self.default_logger_config.level
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        logger.setLevel(level=level)
        formatter = logging.Formatter(
            fmt=self.default_logger_config.log_format,
            datefmt=self.default_logger_config.datefmt,
        )
        if log_file_path:
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        if not propagate:  # 如果不需要传播到父级日志，则添加stream_handler
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
        logger.propagate = propagate
        return logger


def get_logger(
    name: str, level: str = None, log_file_path: str = None, propagate: bool = None
) -> CustomLogger:
    """Get a logger from the global LogManager instance."""
    log_manager = LogManager()
    logger = log_manager.get_logger(name, level, log_file_path, propagate=propagate)
    return logger


__all__ = ["LogManager", "get_logger", "LoggingConfig"]
