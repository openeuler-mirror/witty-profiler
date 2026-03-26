"""编译并构建依赖的二进制文件"""

import argparse
import json
import os
from dataclasses import dataclass

from witty_profiler.common.logging import get_logger
from witty_profiler.config_manager.config_manager import GlobalConfigManager

LOGGER = get_logger(__name__)


@dataclass
class BinaryRecord:
    binary_path: str
    source_path: str
    options: list[str]


class DepBuilder:
    def __init__(self):
        self.config_mngr: GlobalConfigManager = GlobalConfigManager.get_instance()
        self.package_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
        )
        self.binary_records = self._register_binary_records()

    def _register_binary_records(self) -> list[BinaryRecord]:
        config = self.config_mngr.get_config()
        records: list[BinaryRecord] = [
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.cpu_sniffer.cache_miss_monitor_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "cache_monitor_c",
                ),
                options=[
                    "-DCACHE_OUTPUT_MSGSPEC=OFF",
                ],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.cpu_sniffer.cpu_sched_monitor_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "sched_monitor_c",
                ),
                options=[
                    "-DSCHED_OUTPUT_MSGSPEC=OFF",
                ],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.socket_sniffer.socket_sniffer_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "socket_sniffer_c",
                ),
                options=[
                    "-DSOCKET_OUTPUT_MSGSPEC=OFF",
                    "-DSOCKET_LRU_DYNAMIC=OFF",
                ],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.ipc_sniffer.pipe_sniffer_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "pipe_sniffer",
                ),
                options=[],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.ipc_sniffer.uds_sniffer_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "unix_socket_sniffer",
                ),
                options=[],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.ipc_sniffer.sysv_msg_sniffer_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "sysv_msg_sniffer",
                ),
                options=[],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.ipc_sniffer.posix_mq_sniffer_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "posix_mq_sniffer",
                ),
                options=[],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.ipc_sniffer.sysv_sem_sniffer_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "sysv_sem_sniffer",
                ),
                options=[],
            ),
            BinaryRecord(
                binary_path=os.path.abspath(
                    config.sniffer_config.hccs_sniffer.pmu_monitor_binary_path
                ),
                source_path=os.path.join(
                    "witty_profiler",
                    "tools",
                    "ebpftools",
                    "pmu_monitor_c",
                ),
                options=[
                    "-DPMU_OUTPUT_MSGSPEC=OFF",
                ],
            ),
        ]

        return records

    def run(self, force_rebuild: bool = False):
        """编译并构建所有依赖的二进制文件"""
        record2status = []
        for record in self.binary_records:
            status, success_flag = self._build_binary(
                force_rebuild=force_rebuild,
                binary_path=record.binary_path,
                source_path=record.source_path,
                options=record.options,
            )
            record2status.append(
                {
                    "expected_binary": record.binary_path,
                    "status": status,
                }
            )
        LOGGER.report("Build results: %s", json.dumps(record2status, indent=4))

    def verify_binaries(self):
        """验证所有依赖的二进制文件是否存在"""
        verify_success = True
        record2status = []
        for record in self.binary_records:
            if not os.path.exists(record.binary_path):
                LOGGER.error(f"{record.binary_path} does not exist")
                record2status.append(
                    {
                        "expected_binary": record.binary_path,
                        "status": "not exists",
                    }
                )
                verify_success = False
                continue
            try:
                version_info = os.popen(f"{record.binary_path} -v").read().strip()
            except Exception as e:
                LOGGER.error(
                    f"Failed to get version info for {record.binary_path}: {e}"
                )
                record2status.append(
                    {
                        "expected_binary": record.binary_path,
                        "status": "failed to get version info",
                    }
                )
                verify_success = False
                continue
            else:
                LOGGER.info(
                    "%s exists, version info: %s", record.binary_path, version_info
                )
                record2status.append(
                    {
                        "expected_binary": record.binary_path,
                        "status": "success",
                        "version_info": version_info,
                    }
                )
        LOGGER.report("Verification results: %s", json.dumps(record2status, indent=4))
        if not verify_success:
            exit(1)

    def _build_binary(
        self,
        force_rebuild: bool,
        binary_path: str,
        source_path: str,
        options: list[str] = [],
    ) -> tuple[str, bool]:
        """编译并构建单个二进制文件

        Args:
            force_rebuild (bool): 是否强制重新编译
            binary_path (str): 二进制文件路径
            source_path (str): 源文件路径
            options (list[str], optional): 编译选项. Defaults to [].
        Return:
            tuple[str, bool]: 编译结果字符串和成功标志
        """
        dir_path = os.path.dirname(binary_path)
        if os.path.exists(binary_path) and not force_rebuild:
            LOGGER.info(
                "%s exists, skip build "
                "(if you insist to rebuild, please use --force option).",
                binary_path,
            )
            return "build skipped", True

        LOGGER.info("build %s", binary_path)
        """
        cmake --build <dir_path> --target clean
        cmake -B <dir_path> -S <source_path> <options>
        cmake --build <dir_path>
        """
        # create build directory
        os.makedirs(dir_path, exist_ok=True)
        # clean previous build
        try:
            self._try_execute_cmd(
                [
                    "cmake",
                    "--build",
                    dir_path,
                    "--target",
                    "clean",
                ]
            )
        except RuntimeError:
            LOGGER.warning("Clean target failed, could be first build.")

        # cmake configuration
        try:
            self._try_execute_cmd(
                [
                    "cmake",
                    "-B",
                    os.path.abspath(dir_path),
                    "-S",
                    os.path.abspath(
                        os.path.join(
                            self.package_path,
                            source_path,
                        )
                    ),
                    *options,
                ]
            )
        except RuntimeError as e:
            return f"cmake failed for {e}", False

        # build binary
        try:
            self._try_execute_cmd(
                [
                    "cmake",
                    "--build",
                    dir_path,
                ]
            )
        except Exception as e:
            return f"build failed for {e}", False
        return "build succeeded", True

    def _try_execute_cmd(self, cmd: list[str]):
        LOGGER.info(f"Executing command: {' '.join(cmd)}")
        ret = os.system(" ".join(cmd))
        if ret != 0:
            raise RuntimeError(f"Command failed with exit code {ret}: {' '.join(cmd)}")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="配置文件路径",
    )
    parser.add_argument(
        "--verify",
        "-v",
        action="store_true",
        help="验证生成二进制",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force rebuild all dependencies",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="REPORT",
        help="the log level",
    )
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    root_logger = get_logger(name="witty_profiler", level=args.log_level.upper())
    root_logger.setLevel(args.log_level.upper())
    try:
        mngr: GlobalConfigManager = GlobalConfigManager(args.config)
    except Exception as e:
        print(e)
        return
    builder = DepBuilder()
    if args.verify:
        builder.verify_binaries()
    else:
        builder.run(force_rebuild=args.force)


if __name__ == "__main__":
    main()
