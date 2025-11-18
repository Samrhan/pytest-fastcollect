"""
Daemon Client: Communicates with Collection Daemon for instant collection.
"""

import json
import socket
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set


class DaemonClient:
    """Client for communicating with Collection Daemon."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path

    def is_daemon_running(self) -> bool:
        """Check if daemon is running and responsive."""
        try:
            response = self.send_request({"command": "status"}, timeout=1.0)
            return response.get("status") == "running"
        except:
            return False

    def send_request(self, request: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        """Send request to daemon and get response.

        Raises:
            ConnectionError: If cannot connect to daemon
            TimeoutError: If daemon doesn't respond in time
        """
        # Create socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            # Connect to daemon
            sock.connect(self.socket_path)

            # Send request
            request_data = json.dumps(request).encode('utf-8')
            sock.sendall(request_data)

            # Shutdown write side to signal end of request
            sock.shutdown(socket.SHUT_WR)

            # Receive response
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk

            if not response_data:
                raise ConnectionError("Empty response from daemon")

            response = json.loads(response_data.decode('utf-8'))
            return response

        finally:
            sock.close()

    def collect(self, root_path: str, filters: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Request collection from daemon.

        Returns collection results instantly (modules already imported!).
        """
        request = {
            "command": "collect",
            "root_path": root_path,
            "filters": filters or {},
        }

        return self.send_request(request)

    def get_status(self) -> Dict[str, Any]:
        """Get daemon status."""
        return self.send_request({"command": "status"})

    def reload(self, file_paths: Set[str]) -> Dict[str, Any]:
        """Request daemon to reload specified modules."""
        request = {
            "command": "reload",
            "file_paths": list(file_paths),
        }

        return self.send_request(request)

    def stop(self) -> Dict[str, Any]:
        """Stop the daemon."""
        return self.send_request({"command": "stop"}, timeout=2.0)


def get_socket_path(root_path: str) -> str:
    """Get socket path for a project.

    Each project gets its own daemon socket.
    """
    # Use hash of root path to avoid collisions
    import hashlib
    path_hash = hashlib.md5(root_path.encode()).hexdigest()[:8]

    # Store in temp directory
    socket_path = f"/tmp/pytest-fastcollect-{path_hash}.sock"

    return socket_path


def get_pid_file(socket_path: str) -> str:
    """Get PID file path for daemon."""
    return socket_path + ".pid"


def save_daemon_pid(socket_path: str, pid: int):
    """Save daemon PID to file."""
    pid_file = get_pid_file(socket_path)
    with open(pid_file, 'w') as f:
        f.write(str(pid))


def get_daemon_pid(socket_path: str) -> Optional[int]:
    """Get daemon PID from file."""
    pid_file = get_pid_file(socket_path)

    if not os.path.exists(pid_file):
        return None

    try:
        with open(pid_file, 'r') as f:
            return int(f.read().strip())
    except:
        return None


def is_process_running(pid: int) -> bool:
    """Check if process with PID is running."""
    try:
        os.kill(pid, 0)  # Send signal 0 (doesn't kill, just checks)
        return True
    except OSError:
        return False


def stop_daemon(socket_path: str) -> bool:
    """Stop daemon by sending stop command or killing process.

    Returns: True if daemon was stopped
    """
    # Try graceful shutdown first
    try:
        client = DaemonClient(socket_path)
        client.stop()
        time.sleep(0.5)
        return True
    except:
        pass

    # Try killing process
    pid = get_daemon_pid(socket_path)
    if pid and is_process_running(pid):
        try:
            os.kill(pid, 15)  # SIGTERM
            time.sleep(0.5)

            if is_process_running(pid):
                os.kill(pid, 9)  # SIGKILL

            return True
        except:
            pass

    # Clean up stale files
    if os.path.exists(socket_path):
        try:
            os.remove(socket_path)
        except:
            pass

    pid_file = get_pid_file(socket_path)
    if os.path.exists(pid_file):
        try:
            os.remove(pid_file)
        except:
            pass

    return False
