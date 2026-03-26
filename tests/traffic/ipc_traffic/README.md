# IPC 通信采集测试指南

本文档提供每个 IPC 嗅探器的具体测试步骤。

---

## 1. Pipe/FIFO 测试

### 步骤

**窗口1 - 启动采集器**：
```bash
sudo ./src/anansi/binary/pipe/pipe_sniffer -d all -i 2
```

**窗口2 - 执行管道命令**：
```bash
# 简单管道
ls -la | grep "test"

# 多级管道
cat /etc/passwd | head -10 | tail -5
```

**预期结果**：窗口1 输出包含 `write` 和 `read` 方向的数据记录

---

## 2. Unix Domain Socket 测试

### 步骤

**窗口1 - 启动采集器**：
```bash
sudo ./src/anansi/binary/uds/unix_socket_sniffer -d all -i 2
```

**窗口2 - 启动 UDS 服务端**：
```bash
python3 tests/traffic/ipc_traffic/uds_test.py server
```

**窗口3 - 启动 UDS 客户端**：
```bash
python3 tests/traffic/ipc_traffic/uds_test.py client
```

**预期结果**：窗口1 输出包含 `STREAM` 类型的读写记录

---

## 3. System V 消息队列 测试

### 步骤

**窗口1 - 启动采集器**：
```bash
sudo ./src/anansi/binary/sysv_msg/sysv_msg_sniffer -d all -i 2
```

**窗口2 - 运行测试程序**：
```bash
python3 tests/traffic/ipc_traffic/sysv_msg_test.py
```

**预期结果**：窗口1 输出包含 `send` 和 `recv` 方向的消息记录

---

## 4. POSIX 消息队列 测试

### 步骤

**窗口1 - 启动采集器**：
```bash
sudo ./src/anansi/binary/posix_mq/posix_mq_sniffer -d all -i 2
```

**窗口2 - 运行测试程序**：
```bash
python3 tests/traffic/ipc_traffic/posix_mq_test.py
```

**预期结果**：窗口1 输出包含 `/test_mq` 队列的读写记录

---

## 5. System V 信号量 测试

### 步骤

**窗口1 - 启动采集器**：
```bash
sudo ./src/anansi/binary/sysv_sem/sysv_sem_sniffer -i 2
```

**窗口2 - 运行测试程序**：
```bash
python3 tests/traffic/ipc_traffic/sysv_sem_test.py
```

**预期结果**：窗口1 输出包含 `sem_op=-1` (P操作) 和 `sem_op=1` (V操作) 的记录

---

## 快速参考

| 嗅探器 | 二进制路径 | 测试程序 |
|--------|-----------|----------|
| Pipe | `binary/pipe/pipe_sniffer` | `ls \| grep` |
| UDS | `binary/uds/unix_socket_sniffer` | `uds_test.py` |
| SysV MQ | `binary/sysv_msg/sysv_msg_sniffer` | `sysv_msg_test.py` |
| POSIX MQ | `binary/posix_mq/posix_mq_sniffer` | `posix_mq_test.py` |
| SysV Sem | `binary/sysv_sem/sysv_sem_sniffer` | `sysv_sem_test.py` |
