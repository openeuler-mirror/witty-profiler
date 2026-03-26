import io
import os
import shutil
import tempfile
import threading


class RotatedFileStorage:
    def __init__(
        self,
        log_file_path_prefix: str,
        max_size_in_mb: int = 100,
        max_rotation_cnt: int = 3,
    ):
        self._log_file_path_prefix = log_file_path_prefix
        os.makedirs(os.path.dirname(log_file_path_prefix), exist_ok=True)

        self._max_size_in_mb = max_size_in_mb
        self._rotation_cnt = max_rotation_cnt
        self._file_paths = [
            self._log_file_path_prefix + "." + str(i) for i in range(self._rotation_cnt)
        ]
        self._accessing_flag = {i: 0 for i in range(self._rotation_cnt)}
        self._index = 0
        for i in range(self._rotation_cnt):
            if os.path.exists(self._file_paths[i]):
                # remove old log files
                os.remove(self._file_paths[i])
        self._log_fds = [
            open(self._file_paths[i], "a+") for i in range(self._rotation_cnt)
        ]
        self._lock = threading.Lock()

    def __enter__(self):
        """
        进入上下文管理器，获取当前日志文件的访问权限

        在进入上下文时，该方法会执行以下操作：
        1. 检查并旋转日志文件（如果需要）
        2. 增加当前文件的访问计数
        3. 返回当前日志文件对象和文件路径

        Returns:
            当前日志文件的对象（file object）
        """
        with self._lock:
            self._check_size_and_rotate()
            self._accessing_flag[self._index] += 1
            return self._log_fds[self._index]

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self._lock:
            self._accessing_flag[self._index] -= 1
            self._check_size_and_rotate()
        return False

    def _check_size_and_rotate(self):
        """达到大小限制时旋转日志文件"""
        if (
            os.path.getsize(self._file_paths[self._index])
            >= self._max_size_in_mb * 1024 * 1024
        ):
            next_index = (self._index + 1) % self._rotation_cnt
            # 当前文件达到大小限制时，且下一个文件未被访问
            if self._accessing_flag[next_index] == 0:
                self._log_fds[next_index].close()
                open(self._file_paths[next_index], "w").close()  # 清空文件内容
                self._log_fds[next_index] = open(self._file_paths[next_index], "a+")
                self._index = next_index

    def clear_all(self):
        """清空所有日志文件内容"""
        with self._lock:
            for i in range(self._rotation_cnt):
                if self._accessing_flag[i] == 0:
                    self._log_fds[i].close()
                    open(self._file_paths[i], "w").close()
                    self._log_fds[i] = open(self._file_paths[i], "a+")
            self._index = 0

    def get_all_files_as_stream(self):
        class _MergedFileStream:
            def __init__(self, temp_path: str):
                self._temp_path = temp_path
                self._file = None

            def __enter__(self):
                self._file = open(self._temp_path, "r", encoding="utf-8")
                return self._file

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self._file:
                    self._file.close()
                try:
                    os.unlink(self._temp_path)
                except OSError:
                    pass  # 忽略删除失败
                return False

        # 在锁内生成临时合并文件
        with self._lock:
            # 确定读取顺序：从最旧到最新
            file_order = [
                (self._index + 1 + i) % self._rotation_cnt
                for i in range(self._rotation_cnt)
            ]

            # 创建临时文件（在同一目录，避免跨磁盘）
            log_dir = os.path.dirname(self._log_file_path_prefix) or "."
            with tempfile.NamedTemporaryFile(
                mode="w+", delete=False, dir=log_dir, suffix=".merged_log"
            ) as tmp_f:
                temp_path = tmp_f.name
                # 按顺序拼接内容
                for idx in file_order:
                    f = self._log_fds[idx]
                    f.seek(0)
                    # 分块读写，避免大文件内存爆炸
                    while True:
                        chunk = f.read(64 * 1024)  # 64KB 块
                        if not chunk:
                            break
                        tmp_f.write(chunk)

        return _MergedFileStream(temp_path)
