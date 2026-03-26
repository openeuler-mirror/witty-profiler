"""Unix Domain Socket sniffer interface for IPC communication monitoring."""

from dataclasses import dataclass
from typing import Optional, List
import subprocess
import os


@dataclass
class UDSEvent:
    timestamp: int
    pid: int
    tid: int
    inode: int
    socket_type: str
    direction: str
    bytes: int
    count: int
    peer_inode: int


class UDSSniffer:
    """Unix Domain Socket sniffer that monitors AF_UNIX stream and dgram sockets."""
    
    def __init__(self, binary_path: Optional[str] = None):
        if binary_path:
            self.binary_path = binary_path
        else:
            self.binary_path = self._find_binary()
        self._process: Optional[subprocess.Popen] = None
        self._buffer: str = ""
    
    def _find_binary(self) -> str:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ebpftools_dir = os.path.join(os.path.dirname(script_dir), "tools", "ebpftools")
        
        candidates = [
            os.path.join(ebpftools_dir, "unix_socket_sniffer", "unix_socket_sniffer"),
            "unix_socket_sniffer",
        ]
        
        for candidate in candidates:
            if os.path.exists(candidate) or self._is_in_path(candidate):
                return candidate
        
        return "unix_socket_sniffer"
    
    def _is_in_path(self, binary: str) -> bool:
        try:
            result = subprocess.run(
                ["which", binary],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def start(self, pid_filter: Optional[int] = None, interval: int = 1,
              direction: str = "all") -> None:
        """Start the Unix Domain Socket sniffer.
        
        Args:
            pid_filter: Optional PID to filter monitoring
            interval: Sampling interval in seconds
            direction: "send", "recv", or "all"
        """
        if self._process is not None:
            raise RuntimeError("Sniffer is already running")
        
        cmd = [self.binary_path, "-i", str(interval), "-d", direction]
        if pid_filter:
            cmd.extend(["-p", str(pid_filter)])
        
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self._buffer = ""
    
    def get_events(self) -> List[UDSEvent]:
        """Get events from the sniffer.
        
        Returns:
            List of UDSEvent objects
        """
        if self._process is None:
            return []
        
        events = []
        
        try:
            import select
            if self._process.stdout:
                readable, _, _ = select.select([self._process.stdout], [], [], 0.1)
                if readable:
                    data = self._process.stdout.read(4096)
                    self._buffer += data
        except Exception:
            pass
        
        lines = self._buffer.split('\n')
        self._buffer = lines[-1]
        
        for line in lines[:-1]:
            event = self._parse_line(line)
            if event:
                events.append(event)
        
        return events
    
    def _parse_line(self, line: str) -> Optional[UDSEvent]:
        """Parse a CSV output line into a UDSEvent."""
        line = line.strip()
        if not line or line.startswith('timestamp'):
            return None
        
        parts = line.split(',')
        if len(parts) < 9:
            return None
        
        try:
            return UDSEvent(
                timestamp=int(parts[0]),
                pid=int(parts[1]),
                tid=int(parts[2]),
                inode=int(parts[3]),
                socket_type=parts[4],
                direction=parts[5],
                bytes=int(parts[6]),
                count=int(parts[7]),
                peer_inode=int(parts[8])
            )
        except (ValueError, IndexError):
            return None
    
    def stop(self) -> None:
        """Stop the sniffer."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
    
    def is_running(self) -> bool:
        """Check if the sniffer is running."""
        return self._process is not None and self._process.poll() is None
