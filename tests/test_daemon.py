"""
Comprehensive tests for Collection Daemon.

Tests both daemon server and client functionality with:
- Unit tests for individual components
- Integration tests for client-server communication
- Error handling and edge cases
- Performance and stress testing
"""

import os
import sys
import time
import tempfile
import threading
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pytest_fastcollect.daemon import (
    CollectionDaemon,
    DaemonError,
    DaemonValidationError,
    start_daemon,
)
from pytest_fastcollect.daemon_client import (
    DaemonClient,
    ClientError,
    ConnectionError,
    TimeoutError,
    ValidationError,
    get_socket_path,
    save_daemon_pid,
    get_daemon_pid,
    is_process_running,
    stop_daemon,
)


class TestDaemonValidation:
    """Test daemon request validation and security checks."""

    def test_validate_request_valid(self):
        """Test validation of valid requests."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        # Valid requests should not raise
        daemon._validate_request({"command": "status"})
        daemon._validate_request({"command": "collect", "extra": "data"})
        daemon._validate_request({"command": "reload", "file_paths": []})

    def test_validate_request_missing_command(self):
        """Test validation fails for missing command."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        with pytest.raises(DaemonValidationError, match="missing 'command'"):
            daemon._validate_request({})

    def test_validate_request_invalid_command(self):
        """Test validation fails for invalid command."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        with pytest.raises(DaemonValidationError, match="Invalid command"):
            daemon._validate_request({"command": "invalid_command"})

    def test_validate_request_not_dict(self):
        """Test validation fails for non-dict request."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        with pytest.raises(DaemonValidationError, match="must be a dictionary"):
            daemon._validate_request("not a dict")

    def test_validate_file_path_valid(self):
        """Test file path validation for valid paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test Python file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test(): pass")

            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            assert daemon._validate_file_path(str(test_file)) is True

    def test_validate_file_path_nonexistent(self):
        """Test file path validation fails for nonexistent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            assert daemon._validate_file_path("/nonexistent/file.py") is False

    def test_validate_file_path_not_python(self):
        """Test file path validation fails for non-Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("not python")

            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            assert daemon._validate_file_path(str(test_file)) is False

    def test_validate_file_path_outside_root(self):
        """Test file path validation fails for paths outside root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            # Try to access file outside root (directory traversal attack)
            assert daemon._validate_file_path("/etc/passwd") is False


class TestDaemonImports:
    """Test daemon module importing functionality."""

    def test_import_all_modules_success(self):
        """Test successful module import."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test Python files
            test_file1 = Path(tmpdir) / "test1.py"
            test_file1.write_text("def test_one(): pass")

            test_file2 = Path(tmpdir) / "test2.py"
            test_file2.write_text("def test_two(): pass")

            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            file_paths = {str(test_file1), str(test_file2)}
            count = daemon.import_all_modules(file_paths)

            assert count == 2
            assert len(daemon.imported_modules) == 2

    def test_import_all_modules_skip_existing(self):
        """Test that already imported modules are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test(): pass")

            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            file_paths = {str(test_file)}

            # Import once
            count1 = daemon.import_all_modules(file_paths)
            assert count1 == 1

            # Import again - should be skipped
            count2 = daemon.import_all_modules(file_paths)
            assert count2 == 1  # Still counts as success (cached)

    def test_import_all_modules_invalid_file(self):
        """Test that invalid files are logged and skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "invalid.py"
            test_file.write_text("this is not valid python syntax !@#$")

            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            file_paths = {str(test_file)}
            count = daemon.import_all_modules(file_paths)

            # Should fail to import but not crash
            assert count == 0
            assert len(daemon.import_failures) > 0


class TestDaemonRequestHandlers:
    """Test daemon request handler methods."""

    def test_handle_status_request(self):
        """Test status request handler."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        response = daemon.handle_status_request()

        assert response["status"] == "running"
        assert "pid" in response
        assert "uptime" in response
        assert "cached_modules" in response
        assert "metrics" in response

    def test_handle_health_request(self):
        """Test health check request handler."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")
        daemon.running = True

        response = daemon.handle_health_request()

        assert response["status"] in ("healthy", "degraded", "unhealthy")
        assert "checks" in response

    def test_handle_collect_request(self):
        """Test collection request handler."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        response = daemon.handle_collect_request({"command": "collect"})

        assert response["status"] == "success"
        assert "collection_time" in response
        assert "cached_modules" in response

    def test_handle_reload_request(self):
        """Test reload request handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test(): pass")

            daemon = CollectionDaemon(tmpdir, "/tmp/test.sock")

            # Import initially
            daemon.import_all_modules({str(test_file)})
            assert len(daemon.imported_modules) > 0

            # Reload
            response = daemon.handle_reload_request({str(test_file)})

            assert response["status"] == "reloaded"
            assert "modules_reloaded" in response
            assert "reload_time" in response


class TestDaemonClient:
    """Test daemon client functionality."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = DaemonClient("/tmp/test.sock")

        assert client.socket_path == "/tmp/test.sock"
        assert client.max_retries == 3

    def test_client_initialization_invalid_path(self):
        """Test client initialization with invalid path."""
        with pytest.raises(ValidationError):
            DaemonClient("")

    def test_client_validate_request(self):
        """Test client request validation."""
        client = DaemonClient("/tmp/test.sock")

        # Valid request
        client._validate_request({"command": "status"})

        # Invalid requests
        with pytest.raises(ValidationError):
            client._validate_request({})

        with pytest.raises(ValidationError):
            client._validate_request({"command": 123})

    def test_client_retry_logic(self):
        """Test client retry logic with exponential backoff."""
        client = DaemonClient("/tmp/test.sock", max_retries=2)

        # Mock the _send_request_once to always fail
        with patch.object(client, '_send_request_once') as mock_send:
            mock_send.side_effect = ConnectionError("Test error")

            start = time.time()
            with pytest.raises(ConnectionError):
                client.send_request({"command": "status"}, timeout=1.0)
            elapsed = time.time() - start

            # Should have made 3 attempts (initial + 2 retries)
            assert mock_send.call_count == 3

            # Should have exponential backoff delays (0.1s + 0.2s = 0.3s minimum)
            assert elapsed >= 0.3


class TestDaemonHelperFunctions:
    """Test daemon helper functions."""

    def test_get_socket_path(self):
        """Test socket path generation."""
        path1 = get_socket_path("/tmp/project1")
        path2 = get_socket_path("/tmp/project2")

        # Different projects should have different sockets
        assert path1 != path2

        # Same project should have same socket
        assert get_socket_path("/tmp/project1") == path1

    def test_save_and_get_daemon_pid(self):
        """Test saving and retrieving daemon PID."""
        with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
            socket_path = f.name

        try:
            # Save PID
            save_daemon_pid(socket_path, 12345)

            # Retrieve PID
            pid = get_daemon_pid(socket_path)
            assert pid == 12345

        finally:
            # Cleanup
            pid_file = socket_path + ".pid"
            if os.path.exists(pid_file):
                os.remove(pid_file)
            if os.path.exists(socket_path):
                os.remove(socket_path)

    def test_get_daemon_pid_no_file(self):
        """Test getting PID when file doesn't exist."""
        pid = get_daemon_pid("/nonexistent.sock")
        assert pid is None

    def test_is_process_running(self):
        """Test process running check."""
        # Current process should be running
        assert is_process_running(os.getpid()) is True

        # Invalid PID should not be running
        assert is_process_running(0) is False
        assert is_process_running(-1) is False
        assert is_process_running(999999) is False  # Likely doesn't exist


class TestDaemonIntegration:
    """Integration tests for daemon client-server communication."""

    @pytest.fixture
    def daemon_server(self):
        """Start a daemon server for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_path = os.path.join(tmpdir, "test.sock")
            daemon = CollectionDaemon(tmpdir, socket_path)

            # Start daemon in thread
            daemon_thread = threading.Thread(
                target=daemon.start,
                daemon=True
            )
            daemon_thread.start()

            # Wait for daemon to start
            time.sleep(0.5)

            yield socket_path

            # Stop daemon
            daemon.running = False
            time.sleep(0.2)

            # Close logging handlers explicitly (important for Windows file locks)
            for handler in daemon.logger.handlers[:]:
                try:
                    handler.close()
                    daemon.logger.removeHandler(handler)
                except Exception:
                    pass

    def test_client_server_status(self, daemon_server):
        """Test client-server status request."""
        client = DaemonClient(daemon_server)

        response = client.get_status()

        assert response["status"] == "running"
        assert response["pid"] == os.getpid()

    def test_client_server_health(self, daemon_server):
        """Test client-server health check."""
        client = DaemonClient(daemon_server)

        response = client.get_health()

        assert response["status"] in ("healthy", "degraded")

    def test_client_is_daemon_running(self, daemon_server):
        """Test checking if daemon is running."""
        client = DaemonClient(daemon_server)

        assert client.is_daemon_running() is True

        # Non-existent daemon should return False
        client2 = DaemonClient("/nonexistent.sock")
        assert client2.is_daemon_running() is False

    def test_client_connection_timeout(self):
        """Test client connection timeout."""
        client = DaemonClient("/nonexistent.sock", max_retries=1)

        with pytest.raises((ConnectionError, TimeoutError)):
            client.send_request({"command": "status"}, timeout=0.1)


class TestDaemonMetrics:
    """Test daemon metrics and monitoring."""

    def test_metrics_tracking(self):
        """Test that daemon tracks metrics correctly."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        assert daemon.total_requests == 0
        assert daemon.successful_requests == 0
        assert daemon.failed_requests == 0

        # Simulate successful request
        daemon.total_requests += 1
        daemon.successful_requests += 1

        status = daemon.handle_status_request()
        metrics = status["metrics"]

        assert metrics["total_requests"] == 1
        assert metrics["successful_requests"] == 1
        assert metrics["failed_requests"] == 0

    def test_uptime_formatting(self):
        """Test uptime formatting."""
        daemon = CollectionDaemon("/tmp/test", "/tmp/test.sock")

        # Test various durations
        assert daemon._format_uptime(0) == "0s"
        assert daemon._format_uptime(30) == "30s"
        assert daemon._format_uptime(90) == "1m 30s"
        assert daemon._format_uptime(3661) == "1h 1m 1s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
