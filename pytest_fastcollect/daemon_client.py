"""
Daemon Client: Communicates with Collection Daemon for instant collection.

Production Features:
- Comprehensive error handling and retries
- Connection pooling and timeouts
- Request validation
- Detailed error messages
- Health checking
"""

import json
import socket
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Set

from .socket_strategy import create_socket_strategy

# Configure logger
logger = logging.getLogger('pytest_fastcollect.daemon_client')


class ClientError(Exception):
    """Base exception for client errors."""
    pass


class ConnectionError(ClientError):
    """Raised when cannot connect to daemon."""
    pass


class TimeoutError(ClientError):
    """Raised when request times out."""
    pass


class ValidationError(ClientError):
    """Raised when request validation fails."""
    pass


class DaemonClient:
    """Client for communicating with Collection Daemon.

    Production Features:
    - Automatic retries with exponential backoff
    - Comprehensive error handling
    - Request validation
    - Connection timeout management
    - Detailed logging
    """

    def __init__(self, socket_path: str, max_retries: int = 3):
        """Initialize daemon client.

        Args:
            socket_path: Path to Unix domain socket (or base path for TCP mode)
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.socket_path = socket_path
        self.max_retries = max_retries

        # Validate socket path
        if not isinstance(socket_path, str) or not socket_path:
            raise ValidationError("Invalid socket path")

        # Create socket strategy for cross-platform support
        self.socket_strategy = create_socket_strategy(socket_path)

    def is_daemon_running(self) -> bool:
        """Check if daemon is running and responsive.

        Returns:
            True if daemon is healthy and responding, False otherwise

        Note:
            Uses health check if available, falls back to status check
        """
        try:
            # Try health check first
            response = self.send_request(
                {"command": "health"},
                timeout=1.0,
                retries=1
            )
            return response.get("status") in ("healthy", "degraded")
        except:
            # Fall back to status check
            try:
                response = self.send_request(
                    {"command": "status"},
                    timeout=1.0,
                    retries=1
                )
                return response.get("status") == "running"
            except:
                return False

    def _validate_request(self, request: Dict[str, Any]) -> None:
        """Validate request before sending.

        Args:
            request: Request dictionary to validate

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(request, dict):
            raise ValidationError("Request must be a dictionary")

        if "command" not in request:
            raise ValidationError("Request missing 'command' field")

        if not isinstance(request["command"], str):
            raise ValidationError("Command must be a string")

    def send_request(
        self,
        request: Dict[str, Any],
        timeout: float = 5.0,
        retries: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send request to daemon and get response with automatic retries.

        Args:
            request: Request dictionary with command and parameters
            timeout: Request timeout in seconds
            retries: Number of retry attempts (uses self.max_retries if not specified)

        Returns:
            Response dictionary from daemon

        Raises:
            ValidationError: If request validation fails
            ConnectionError: If cannot connect to daemon after all retries
            TimeoutError: If daemon doesn't respond in time
            ClientError: For other errors

        Note:
            - Automatically retries failed requests with exponential backoff
            - Validates requests before sending
            - Provides detailed error messages
        """
        # Validate request
        self._validate_request(request)

        # Use default retries if not specified
        if retries is None:
            retries = self.max_retries

        last_exception = None
        for attempt in range(retries + 1):
            try:
                return self._send_request_once(request, timeout)

            except socket.timeout as e:
                last_exception = TimeoutError(
                    f"Daemon request timed out after {timeout}s"
                )
                logger.warning(
                    f"Request timed out (attempt {attempt + 1}/{retries + 1})"
                )

            except socket.error as e:
                if e.errno == 2 or e.errno == 111:  # ENOENT or ECONNREFUSED
                    last_exception = ConnectionError(
                        f"Cannot connect to daemon at {self.socket_path}. "
                        f"Is the daemon running?"
                    )
                else:
                    last_exception = ConnectionError(
                        f"Socket error connecting to daemon: {e}"
                    )
                logger.warning(
                    f"Connection failed (attempt {attempt + 1}/{retries + 1}): {e}"
                )

            except ClientError as e:
                # Already a client error (ConnectionError, TimeoutError, ValidationError, etc.)
                # Preserve it and continue retrying
                last_exception = e
                logger.warning(
                    f"Client error (attempt {attempt + 1}/{retries + 1}): {e}"
                )

            except Exception as e:
                last_exception = ClientError(f"Unexpected error: {e}")
                logger.error(
                    f"Unexpected error (attempt {attempt + 1}/{retries + 1}): {e}",
                    exc_info=True
                )

            # Don't sleep after last attempt
            if attempt < retries:
                # Exponential backoff: 0.1s, 0.2s, 0.4s, ...
                sleep_time = 0.1 * (2 ** attempt)
                logger.debug(f"Retrying in {sleep_time}s...")
                time.sleep(sleep_time)

        # All retries exhausted
        if last_exception:
            raise last_exception
        else:
            raise ClientError("All retry attempts failed")

    def _send_request_once(
        self,
        request: Dict[str, Any],
        timeout: float
    ) -> Dict[str, Any]:
        """Send a single request without retries.

        Args:
            request: Request dictionary
            timeout: Request timeout in seconds

        Returns:
            Response dictionary from daemon

        Raises:
            Various socket exceptions that will be caught by send_request
        """
        # Create and connect socket using strategy
        sock = self.socket_strategy.create_client_socket(timeout)

        try:

            # Send request
            request_data = json.dumps(request).encode('utf-8')
            sock.sendall(request_data)
            logger.debug(f"Sent request: {request.get('command')}")

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

            # Parse response
            try:
                response = json.loads(response_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                raise ClientError(f"Invalid JSON response from daemon: {e}")

            logger.debug(f"Received response: {response.get('status')}")
            return response

        finally:
            try:
                sock.close()
            except:
                pass

    def collect(
        self,
        root_path: str,
        filters: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Request collection from daemon.

        Args:
            root_path: Root directory for collection
            filters: Optional filters for collection

        Returns:
            Collection results with timing and module information

        Note:
            Since modules are pre-imported in daemon, this is nearly instant!
        """
        request = {
            "command": "collect",
            "root_path": root_path,
            "filters": filters or {},
        }

        logger.info(f"Requesting collection for {root_path}")
        response = self.send_request(request)
        logger.info(
            f"Collection completed in {response.get('collection_time', 0):.4f}s"
        )
        return response

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive daemon status.

        Returns:
            Status dict including:
            - status: "running" or error
            - pid: Process ID
            - uptime: Seconds since start
            - cached_modules: Number of imported modules
            - metrics: Request statistics
        """
        logger.debug("Requesting daemon status")
        return self.send_request({"command": "status"})

    def get_health(self) -> Dict[str, Any]:
        """Get daemon health check.

        Returns:
            Health check result with diagnostics
        """
        logger.debug("Requesting daemon health check")
        return self.send_request({"command": "health"})

    def reload(self, file_paths: Set[str]) -> Dict[str, Any]:
        """Request daemon to reload specified modules.

        Args:
            file_paths: Set of file paths to reload

        Returns:
            Reload result with timing and counts

        Note:
            This clears cached modules and re-imports them
        """
        if not file_paths:
            raise ValidationError("file_paths cannot be empty")

        request = {
            "command": "reload",
            "file_paths": list(file_paths),
        }

        logger.info(f"Requesting reload of {len(file_paths)} modules")
        response = self.send_request(request)
        logger.info(
            f"Reload completed: {response.get('modules_reloaded', 0)} modules "
            f"in {response.get('reload_time', 0):.2f}s"
        )
        return response

    def stop(self) -> Dict[str, Any]:
        """Stop the daemon gracefully.

        Returns:
            Stop confirmation

        Note:
            Daemon will clean up resources and exit
        """
        logger.info("Requesting daemon stop")
        return self.send_request({"command": "stop"}, timeout=2.0)


def get_socket_path(root_path: str) -> str:
    """Get socket path for a project.

    Each project gets its own daemon socket based on root path hash.

    Args:
        root_path: Project root directory path

    Returns:
        Path to Unix domain socket for this project

    Note:
        Uses MD5 hash of root path to ensure unique socket per project
    """
    # Use hash of root path to avoid collisions
    import hashlib

    # Resolve to absolute path for consistency
    resolved_path = str(Path(root_path).resolve())
    path_hash = hashlib.md5(resolved_path.encode()).hexdigest()[:8]

    # Store in temp directory
    socket_path = f"/tmp/pytest-fastcollect-{path_hash}.sock"

    return socket_path


def get_pid_file(socket_path: str) -> str:
    """Get PID file path for daemon.

    Args:
        socket_path: Path to daemon socket

    Returns:
        Path to PID file (socket_path + ".pid")
    """
    return socket_path + ".pid"


def save_daemon_pid(socket_path: str, pid: int) -> None:
    """Save daemon PID to file.

    Args:
        socket_path: Path to daemon socket
        pid: Process ID to save

    Note:
        Creates PID file next to socket file
    """
    pid_file = get_pid_file(socket_path)
    try:
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        logger.debug(f"Saved daemon PID {pid} to {pid_file}")
    except Exception as e:
        logger.error(f"Failed to save PID file: {e}")
        raise


def get_daemon_pid(socket_path: str) -> Optional[int]:
    """Get daemon PID from file.

    Args:
        socket_path: Path to daemon socket

    Returns:
        PID if found and valid, None otherwise

    Note:
        Returns None if PID file doesn't exist or contains invalid data
    """
    pid_file = get_pid_file(socket_path)

    if not os.path.exists(pid_file):
        return None

    try:
        with open(pid_file, 'r') as f:
            pid_str = f.read().strip()
            pid = int(pid_str)
            if pid > 0:
                return pid
            else:
                logger.warning(f"Invalid PID in file: {pid}")
                return None
    except (ValueError, OSError) as e:
        logger.warning(f"Failed to read PID file: {e}")
        return None


def is_process_running(pid: int) -> bool:
    """Check if process with given PID is running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise

    Note:
        Uses platform-specific methods to check process existence
    """
    if pid <= 0:
        return False

    import sys

    if sys.platform == 'win32':
        # On Windows, use tasklist command
        try:
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return str(pid) in result.stdout
        except Exception:
            # If tasklist fails, assume process doesn't exist
            return False
    else:
        # On Unix, use os.kill with signal 0
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def stop_daemon(socket_path: str) -> bool:
    """Stop daemon gracefully or forcefully.

    Tries multiple approaches in order:
    1. Send stop command via socket (graceful)
    2. Send SIGTERM to process (graceful)
    3. Send SIGKILL to process (forceful)
    4. Clean up stale files

    Args:
        socket_path: Path to daemon socket

    Returns:
        True if daemon was stopped (or wasn't running), False on failure

    Note:
        Always cleans up stale socket and PID files
    """
    logger.info(f"Stopping daemon at {socket_path}")

    daemon_was_running = False

    # Try graceful shutdown via socket first
    try:
        client = DaemonClient(socket_path, max_retries=1)
        client.stop()
        time.sleep(0.5)
        daemon_was_running = True
        logger.info("Daemon stopped via stop command")

        # Check if actually stopped
        if not os.path.exists(socket_path):
            return True
    except Exception as e:
        logger.debug(f"Could not stop via socket: {e}")

    # Try killing process
    pid = get_daemon_pid(socket_path)
    if pid and is_process_running(pid):
        daemon_was_running = True
        try:
            # Send SIGTERM (graceful shutdown)
            logger.info(f"Sending SIGTERM to daemon PID {pid}")
            os.kill(pid, 15)
            time.sleep(0.5)

            # Check if still running
            if is_process_running(pid):
                # Send SIGKILL (forced shutdown)
                logger.warning(f"Daemon didn't stop, sending SIGKILL to PID {pid}")
                os.kill(pid, 9)
                time.sleep(0.2)

            logger.info(f"Daemon process {pid} stopped")
        except OSError as e:
            logger.error(f"Failed to kill daemon process: {e}")

    # Clean up stale files
    cleaned = False

    if os.path.exists(socket_path):
        try:
            os.remove(socket_path)
            logger.debug(f"Removed socket file: {socket_path}")
            cleaned = True
        except Exception as e:
            logger.error(f"Failed to remove socket file: {e}")

    pid_file = get_pid_file(socket_path)
    if os.path.exists(pid_file):
        try:
            os.remove(pid_file)
            logger.debug(f"Removed PID file: {pid_file}")
            cleaned = True
        except Exception as e:
            logger.error(f"Failed to remove PID file: {e}")

    return daemon_was_running or cleaned
