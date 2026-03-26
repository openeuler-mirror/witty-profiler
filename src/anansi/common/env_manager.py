"""Environment information management for Anansi framework.

Provides EnvManager singleton that detects and caches system environment
information including local IP, hostname, and machine ID. Used for remote
collector namespacing and HTTP API response envelopes.

Key Components:
    - EnvInfo: Dataclass containing environment metadata
    - EnvManager: Singleton providing cached environment detection

Environment Detection:
    - local_ip: Primary network interface IP (via socket connection test)
    - hostname: System hostname from socket.gethostname()
    - machine_id: Unique machine identifier from /etc/machine-id or UUID

Usage:
    ```python
    env_mgr = EnvManager.get_instance()
    env_info = env_mgr.get_env_info()
    print(f"Running on {env_info.hostname} ({env_info.local_ip})")

    # FastAPI response envelope
    response = {"env": env_mgr.get_env_dict(), "content": data}
    ```

Caching:
    Environment values are cached after first detection. Use refresh=True
    to force re-detection if network configuration changes.

Notes:
    fastapi_available() checks if FastAPI is importable without raising errors.
    Used by server backend selection logic.
"""

import socket
import subprocess
import uuid
import importlib.util

from dataclasses import dataclass, field, asdict

from anansi.common.logging import get_logger
from anansi.common.singleton import Singleton

LOGGER = get_logger(__name__)


@dataclass
class EnvInfo:
    local_ip: str = None
    hostname: str = None
    machine_id: str = None

    def __post_init__(self):
        self.local_ip = str(self.local_ip)
        self.hostname = str(self.hostname)
        self.machine_id = str(self.machine_id)
        self._model_dict = asdict(self)

    def model_dump(self):
        return self._model_dict


class EnvManager(Singleton):
    def __init__(self):
        self.__local_ip = None
        self.__msgspec_compatible = None
        self.__hostname = None
        self.__machine_id = None
        self.__env_info = None
        self.__fastapi_available = None
        self.__gpu_available = None
        self.__npu_available = None
        self.__cpu_info = None
        self.__is_kunpeng_920 = None

    def get_env_dict(self, refresh=False) -> dict:
        env_info = self.get_env_info(refresh=refresh)
        return env_info.model_dump()

    def get_env_info(self, refresh=False) -> EnvInfo:
        if self.__env_info is not None and not refresh:
            return self.__env_info
        self.__env_info = EnvInfo(
            local_ip=self.get_local_ip(refresh=refresh),
            hostname=self.get_hostname(refresh=refresh),
            machine_id=self.get_machine_id(refresh=refresh),
        )
        return self.__env_info

    def get_local_ip(self, refresh=False):
        if self.__local_ip is not None and not refresh:
            return self.__local_ip
        try:
            print("Detecting local IP address...")
            # 创建一个 UDP 套接字（不实际发送数据）
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # 连接到一个远程地址（不会真正连接）
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            self.__local_ip = ip
            return ip
        except Exception:
            self.__local_ip = None
            return None

    def msgspec_compatible(self, refresh=False) -> bool:
        """
        判断当前环境是否兼容 msgspec
        """
        if self.__msgspec_compatible is not None and not refresh:
            return self.__msgspec_compatible
        try:
            import msgspec

            # 定义一个简单 Struct
            class Test(msgspec.Struct):
                x: int

            # 编码 + 解码 round-trip
            obj = Test(42)
            data = msgspec.msgpack.encode(obj)
            restored = msgspec.msgpack.decode(data, type=Test)
            self.__msgspec_compatible = restored.x == 42
            if self.__msgspec_compatible:
                LOGGER.debug("msgspec is fully functional.")
            else:
                LOGGER.debug("msgspec returned incorrect data.")
        except Exception as e:
            LOGGER.error("msgspec failed at runtime: %s", e)
            self.__msgspec_compatible = False
        return self.__msgspec_compatible

    def get_hostname(self, refresh=False) -> str:
        """
        获取主机名
        """
        if self.__hostname is not None and not refresh:
            return self.__hostname
        self.__hostname = socket.gethostname()
        return self.__hostname

    def get_machine_id(self, refresh=False) -> str:
        """
        通过/etc/machine-id获取机器ID
        """
        if self.__machine_id is not None and not refresh:
            return self.__machine_id
        try:
            with open("/etc/machine-id", "r") as f:
                self.__machine_id = f.read().strip()
        except Exception:
            self.__machine_id = "unknown_random_{}".format(uuid.uuid4().hex[:8])
        return self.__machine_id

    def fastapi_available(self, refresh=False) -> bool:
        """
        判断当前环境是否兼容 FastAPI
        """
        if self.__fastapi_available is not None and not refresh:
            return self.__fastapi_available

        try:
            import uvicorn
            from fastapi import FastAPI, HTTPException, Request
            from fastapi.responses import (
                JSONResponse,
                PlainTextResponse,
                RedirectResponse,
            )

            self.__fastapi_available = True
        except ImportError:
            LOGGER.debug(
                "FastAPI/uvicorn not available, skipping FastAPIServer registration"
            )

            self.__fastapi_available = False
        return self.__fastapi_available

    def gpu_available(self, refresh=False) -> bool:
        if self.__gpu_available is not None and not refresh:
            return self.__gpu_available

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.__gpu_available = result.returncode == 0 and bool(
                result.stdout.strip()
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            self.__gpu_available = False

        return self.__gpu_available

    def has_gpu(self, refresh=False) -> bool:
        return self.gpu_available(refresh=refresh)

    def npu_available(self, refresh=False) -> bool:
        if self.__npu_available is not None and not refresh:
            return self.__npu_available

        try:
            result = subprocess.run(
                ["npu-smi", "info", "-t", "topo"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                self.__npu_available = False
            else:
                lines = [line.strip() for line in result.stdout.splitlines()]
                self.__npu_available = any(
                    line.startswith("NPU") and line[3:4].isdigit() for line in lines
                )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            self.__npu_available = False

        return self.__npu_available

    def has_npu(self, refresh=False) -> bool:
        return self.npu_available(refresh=refresh)

    def get_cpu_info(self, refresh=False) -> dict:
        """Detect CPU vendor and model information.

        Returns a dict with keys:
            - vendor: str or None (e.g., 'HiSilicon', 'Intel', 'AMD')
            - model: str or None (e.g., 'Kunpeng 920', 'Xeon Gold 6258R')
            - is_kunpeng_920: bool (True if detected as Huawei Kunpeng 920)
            - arch: str or None (e.g., 'aarch64', 'x86_64')
            - implementer: str or None (ARM CPU implementer hex code)
            - part: str or None (ARM CPU part hex code)

        Detection methods tried in order:
        1. /proc/cpuinfo parsing (ARM and x86 formats)
        2. lscpu command output
        3. /sys/devices/virtual/dmi/id/product_name (DMI product name)
        4. /proc/device-tree/model (ARM device tree)
        """
        if self.__cpu_info is not None and not refresh:
            return self.__cpu_info

        info = {
            "vendor": None,
            "model": None,
            "is_kunpeng_920": False,
            "arch": None,
            "implementer": None,
            "part": None,
        }

        # Helper to check if string contains Kunpeng/Huawei indicators
        def is_kunpeng_indicator(s: str) -> bool:
            if not s:
                return False
            s_lower = s.lower()
            return any(
                indicator in s_lower
                for indicator in [
                    "kunpeng",
                    "hisilicon",
                    "hisi",
                    "huawei",
                    "hi16",
                    "hi1616",
                ]
            )

        # Method 1: /proc/cpuinfo
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
                content = f.read()

            # Parse key-value pairs (both ARM and x86 formats)
            cpuinfo = {}
            for line in content.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    cpuinfo[key] = value

            # Check various fields for vendor/model info
            for field in [
                "model name",
                "Hardware",
                "Processor",
                "vendor_id",
                "Vendor ID",
            ]:
                if field in cpuinfo:
                    value = cpuinfo[field]
                    if is_kunpeng_indicator(value):
                        info["is_kunpeng_920"] = True
                        info["vendor"] = "HiSilicon"
                        info["model"] = value
                        break

            # ARM-specific fields
            if "CPU implementer" in cpuinfo:
                info["implementer"] = cpuinfo["CPU implementer"]
                # HiSilicon implementer code is often 0x48
                if cpuinfo["CPU implementer"] == "0x48":
                    info["vendor"] = "HiSilicon"
                    info["is_kunpeng_920"] = True

            if "CPU part" in cpuinfo:
                info["part"] = cpuinfo["CPU part"]

            # Architecture detection
            if "CPU architecture" in cpuinfo:
                arch_code = cpuinfo["CPU architecture"]
                # Map ARM architecture codes
                if arch_code == "8":
                    info["arch"] = "aarch64"
                elif arch_code == "7":
                    info["arch"] = "armv7l"
            elif "flags" in cpuinfo and "lm" in cpuinfo["flags"]:
                # x86_64 with Long Mode
                info["arch"] = "x86_64"

        except (OSError, UnicodeDecodeError):
            pass  # /proc/cpuinfo not accessible

        # If still no vendor/model detection, try lscpu
        if not info["vendor"] and not info["model"]:
            try:
                result = subprocess.run(
                    ["lscpu"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0:
                    lscpu_output = result.stdout
                    for line in lscpu_output.splitlines():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip()
                            if key in ["Model name", "Vendor ID", "Architecture"]:
                                if is_kunpeng_indicator(value):
                                    info["is_kunpeng_920"] = True
                                    info["vendor"] = "HiSilicon"
                                    info["model"] = value
                                elif key == "Architecture":
                                    info["arch"] = value
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        # Try DMI sysfs for product name
        try:
            with open(
                "/sys/devices/virtual/dmi/id/product_name", "r", encoding="utf-8"
            ) as f:
                product_name = f.read().strip()
                if is_kunpeng_indicator(product_name):
                    info["is_kunpeng_920"] = True
                    info["vendor"] = "HiSilicon"
                    info["model"] = product_name
        except (OSError, UnicodeDecodeError):
            pass

        # Try device tree model (ARM)
        try:
            with open("/proc/device-tree/model", "r", encoding="utf-8") as f:
                model = f.read().strip().rstrip("\x00")
                if is_kunpeng_indicator(model):
                    info["is_kunpeng_920"] = True
                    info["vendor"] = "HiSilicon"
                    info["model"] = model
        except (OSError, UnicodeDecodeError):
            pass

        # Final fallback: check uname -m for architecture
        if not info["arch"]:
            try:
                result = subprocess.run(
                    ["uname", "-m"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0:
                    info["arch"] = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

        # Cache the result
        self.__cpu_info = info
        self.__is_kunpeng_920 = info["is_kunpeng_920"]
        return info

    def is_kunpeng_920(self, refresh=False) -> bool:
        """Check if the current CPU is Huawei Kunpeng 920."""
        if self.__is_kunpeng_920 is not None and not refresh:
            return self.__is_kunpeng_920

        # This will populate both caches
        self.get_cpu_info(refresh=refresh)
        return self.__is_kunpeng_920

    @staticmethod
    def is_package_installed(package_name: str) -> bool:
        """
        判断指定的Python包是否已安装
        """
        try:
            result = importlib.util.find_spec(package_name)
            return result is not None
        except ImportError:
            return False


__all__ = ["EnvManager", "EnvInfo"]
