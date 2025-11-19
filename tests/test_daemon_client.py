"""
Comprehensive unit tests for DaemonClient module.

This test suite focuses specifically on daemon_client.py functionality:
- DaemonClient methods (collect, reload, stop, get_status, get_health)
- Helper functions (get_socket_path, get_pid_file, PID management, stop_daemon)
- Error handling and edge cases
- Socket communication and cleanup
- Retry logic and timeouts
"""

import os
import sys
import time
import json
import socket
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pytest_fastcollect.daemon_client import (
    DaemonClient,
    ClientError,
    ConnectionError,
    TimeoutError,
    ValidationError,
    get_socket_path,
    get_pid_file,
    save_daemon_pid,
    get_daemon_pid,
    is_process_running,
    stop_daemon,
)


class TestDaemonClientInitialization:
    """Test DaemonClient initialization and validation."""

    def test_initialization_valid_socket_path(self):
        """Test initialization with valid socket path."""
        client = DaemonClient("/tmp/test.sock")
        assert client.socket_path == "/tmp/test.sock"
        assert client.max_retries == 3

    def test_initialization_custom_retries(self):
        """Test initialization with custom retry count."""
        client = DaemonClient("/tmp/test.sock", max_retries=5)
        assert client.max_retries == 5

    def test_initialization_empty_socket_path(self):
        """Test initialization fails with empty socket path."""
        with pytest.raises(ValidationError, match="Invalid socket path"):
            DaemonClient("")

    def test_initialization_none_socket_path(self):
        """Test initialization fails with None socket path."""
        with pytest.raises((ValidationError, TypeError)):
            DaemonClient(None)

    def test_initialization_non_string_socket_path(self):
        """Test initialization fails with non-string socket path."""
        with pytest.raises((ValidationError, TypeError)):
            DaemonClient(12345)


class TestDaemonClientRequestValidation:
    """Test DaemonClient request validation."""

    def test_validate_request_valid(self):
        """Test validation passes for valid requests."""
        client = DaemonClient("/tmp/test.sock")

        # These should not raise
        client._validate_request({"command": "status"})
        client._validate_request({"command": "collect", "root_path": "/tmp"})
        client._validate_request({"command": "reload", "file_paths": []})

    def test_validate_request_missing_command(self):
        """Test validation fails when command is missing."""
        client = DaemonClient("/tmp/test.sock")

        with pytest.raises(ValidationError, match="missing 'command'"):
            client._validate_request({})

    def test_validate_request_command_not_string(self):
        """Test validation fails when command is not a string."""
        client = DaemonClient("/tmp/test.sock")

        with pytest.raises(ValidationError, match="Command must be a string"):
            client._validate_request({"command": 123})

        with pytest.raises(ValidationError, match="Command must be a string"):
            client._validate_request({"command": None})

        with pytest.raises(ValidationError, match="Command must be a string"):
            client._validate_request({"command": ["status"]})

    def test_validate_request_not_dict(self):
        """Test validation fails when request is not a dictionary."""
        client = DaemonClient("/tmp/test.sock")

        with pytest.raises(ValidationError, match="must be a dictionary"):
            client._validate_request("not a dict")

        with pytest.raises(ValidationError, match="must be a dictionary"):
            client._validate_request(["command", "status"])

        with pytest.raises(ValidationError, match="must be a dictionary"):
            client._validate_request(None)


class TestDaemonClientSendRequest:
    """Test DaemonClient send_request functionality."""

    def test_send_request_success(self):
        """Test successful request send."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {"status": "success", "data": "test"}

        with patch.object(client, '_send_request_once', return_value=mock_response):
            response = client.send_request({"command": "status"})
            assert response == mock_response

    def test_send_request_with_custom_timeout(self):
        """Test send_request respects custom timeout."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {"status": "success"}

        with patch.object(client, '_send_request_once', return_value=mock_response) as mock_send:
            client.send_request({"command": "status"}, timeout=10.0)
            mock_send.assert_called_once_with({"command": "status"}, 10.0)

    def test_send_request_with_custom_retries(self):
        """Test send_request respects custom retry count."""
        client = DaemonClient("/tmp/test.sock", max_retries=3)

        with patch.object(client, '_send_request_once') as mock_send:
            mock_send.side_effect = socket.error(111, "Connection refused")

            with pytest.raises(ConnectionError):
                client.send_request({"command": "status"}, retries=2)

            # Should be 3 attempts (initial + 2 retries)
            assert mock_send.call_count == 3

    def test_send_request_retry_on_timeout(self):
        """Test retry logic on timeout errors."""
        client = DaemonClient("/tmp/test.sock", max_retries=2)

        with patch.object(client, '_send_request_once') as mock_send:
            mock_send.side_effect = socket.timeout("Timed out")

            with pytest.raises(TimeoutError, match="timed out"):
                client.send_request({"command": "status"}, timeout=1.0)

            # Should retry (3 total attempts)
            assert mock_send.call_count == 3

    def test_send_request_retry_on_connection_error(self):
        """Test retry logic on connection errors."""
        client = DaemonClient("/tmp/test.sock", max_retries=2)

        with patch.object(client, '_send_request_once') as mock_send:
            # Simulate connection refused (errno 111)
            mock_send.side_effect = socket.error(111, "Connection refused")

            with pytest.raises(ConnectionError, match="Cannot connect"):
                client.send_request({"command": "status"})

            assert mock_send.call_count == 3

    def test_send_request_retry_on_enoent(self):
        """Test retry logic on ENOENT error (socket doesn't exist)."""
        client = DaemonClient("/tmp/test.sock", max_retries=2)

        with patch.object(client, '_send_request_once') as mock_send:
            # Simulate file not found (errno 2)
            mock_send.side_effect = socket.error(2, "No such file")

            with pytest.raises(ConnectionError, match="Cannot connect"):
                client.send_request({"command": "status"})

            assert mock_send.call_count == 3

    def test_send_request_exponential_backoff(self):
        """Test exponential backoff between retries."""
        client = DaemonClient("/tmp/test.sock", max_retries=2)

        with patch.object(client, '_send_request_once') as mock_send:
            with patch('time.sleep') as mock_sleep:
                mock_send.side_effect = socket.error(111, "Connection refused")

                with pytest.raises(ConnectionError):
                    client.send_request({"command": "status"})

                # Should have 2 sleep calls (after first and second attempt)
                assert mock_sleep.call_count == 2

                # Check exponential backoff: 0.1s, 0.2s
                calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert calls[0] == 0.1
                assert calls[1] == 0.2

    def test_send_request_success_after_retry(self):
        """Test successful request after initial failures."""
        client = DaemonClient("/tmp/test.sock", max_retries=2)

        mock_response = {"status": "success"}

        with patch.object(client, '_send_request_once') as mock_send:
            # Fail twice, then succeed
            mock_send.side_effect = [
                socket.error(111, "Connection refused"),
                socket.error(111, "Connection refused"),
                mock_response
            ]

            response = client.send_request({"command": "status"})
            assert response == mock_response
            assert mock_send.call_count == 3

    def test_send_request_validation_error_no_retry(self):
        """Test validation errors are raised immediately without retry."""
        client = DaemonClient("/tmp/test.sock", max_retries=3)

        with patch.object(client, '_send_request_once') as mock_send:
            # Request validation should fail before _send_request_once
            with pytest.raises(ValidationError):
                client.send_request({})  # Missing command

            # Should not even call _send_request_once
            assert mock_send.call_count == 0

    def test_send_request_unexpected_error(self):
        """Test handling of unexpected errors."""
        client = DaemonClient("/tmp/test.sock", max_retries=1)

        with patch.object(client, '_send_request_once') as mock_send:
            mock_send.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(ClientError, match="Unexpected error"):
                client.send_request({"command": "status"})


class TestDaemonClientSendRequestOnce:
    """Test DaemonClient _send_request_once internal method."""

    def test_send_request_once_success(self):
        """Test successful single request."""
        client = DaemonClient("/tmp/test.sock")

        mock_socket = MagicMock()
        mock_response = {"status": "success", "data": "test"}
        mock_socket.recv.side_effect = [
            json.dumps(mock_response).encode('utf-8'),
            b""  # End of stream
        ]

        with patch.object(client.socket_strategy, 'create_client_socket', return_value=mock_socket):
            response = client._send_request_once({"command": "status"}, timeout=5.0)

            assert response == mock_response
            mock_socket.sendall.assert_called_once()
            mock_socket.shutdown.assert_called_once_with(socket.SHUT_WR)
            mock_socket.close.assert_called_once()

    def test_send_request_once_empty_response(self):
        """Test handling of empty response."""
        client = DaemonClient("/tmp/test.sock")

        mock_socket = MagicMock()
        mock_socket.recv.return_value = b""  # Empty response

        with patch.object(client.socket_strategy, 'create_client_socket', return_value=mock_socket):
            with pytest.raises(ConnectionError, match="Empty response"):
                client._send_request_once({"command": "status"}, timeout=5.0)

    def test_send_request_once_invalid_json(self):
        """Test handling of invalid JSON response."""
        client = DaemonClient("/tmp/test.sock")

        mock_socket = MagicMock()
        mock_socket.recv.side_effect = [
            b"not valid json {{{",
            b""
        ]

        with patch.object(client.socket_strategy, 'create_client_socket', return_value=mock_socket):
            with pytest.raises(ClientError, match="Invalid JSON response"):
                client._send_request_once({"command": "status"}, timeout=5.0)

    def test_send_request_once_chunked_response(self):
        """Test handling of response received in multiple chunks."""
        client = DaemonClient("/tmp/test.sock")

        mock_socket = MagicMock()
        response_data = {"status": "success", "large_data": "x" * 10000}
        response_json = json.dumps(response_data).encode('utf-8')

        # Split response into chunks
        chunk_size = 4096
        chunks = [response_json[i:i+chunk_size] for i in range(0, len(response_json), chunk_size)]
        chunks.append(b"")  # End of stream

        mock_socket.recv.side_effect = chunks

        with patch.object(client.socket_strategy, 'create_client_socket', return_value=mock_socket):
            response = client._send_request_once({"command": "status"}, timeout=5.0)

            assert response == response_data

    def test_send_request_once_socket_cleanup_on_error(self):
        """Test socket is closed even when error occurs."""
        client = DaemonClient("/tmp/test.sock")

        mock_socket = MagicMock()
        mock_socket.sendall.side_effect = socket.error("Send failed")

        with patch.object(client.socket_strategy, 'create_client_socket', return_value=mock_socket):
            with pytest.raises(socket.error):
                client._send_request_once({"command": "status"}, timeout=5.0)

            # Socket should still be closed
            mock_socket.close.assert_called_once()


class TestDaemonClientMethods:
    """Test DaemonClient high-level methods."""

    def test_is_daemon_running_health_check(self):
        """Test is_daemon_running using health check."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {"status": "healthy"}

        with patch.object(client, 'send_request', return_value=mock_response):
            assert client.is_daemon_running() is True

    def test_is_daemon_running_degraded(self):
        """Test is_daemon_running returns True for degraded status."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {"status": "degraded"}

        with patch.object(client, 'send_request', return_value=mock_response):
            assert client.is_daemon_running() is True

    def test_is_daemon_running_fallback_to_status(self):
        """Test fallback to status check when health fails."""
        client = DaemonClient("/tmp/test.sock")

        with patch.object(client, 'send_request') as mock_send:
            # Health check fails, status check succeeds
            mock_send.side_effect = [
                Exception("Health not supported"),
                {"status": "running"}
            ]

            assert client.is_daemon_running() is True

    def test_is_daemon_running_not_running(self):
        """Test is_daemon_running returns False when daemon is down."""
        client = DaemonClient("/tmp/test.sock")

        with patch.object(client, 'send_request', side_effect=ConnectionError("Not running")):
            assert client.is_daemon_running() is False

    def test_collect_method(self):
        """Test collect method sends correct request."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {
            "status": "success",
            "collection_time": 0.123,
            "items": []
        }

        with patch.object(client, 'send_request', return_value=mock_response) as mock_send:
            response = client.collect("/tmp/project")

            mock_send.assert_called_once()
            request = mock_send.call_args[0][0]
            assert request["command"] == "collect"
            assert request["root_path"] == "/tmp/project"
            assert request["filters"] == {}

            assert response == mock_response

    def test_collect_method_with_filters(self):
        """Test collect method with filters."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {"status": "success", "collection_time": 0.1}
        filters = {"keyword": "test", "marker": "slow"}

        with patch.object(client, 'send_request', return_value=mock_response) as mock_send:
            client.collect("/tmp/project", filters=filters)

            request = mock_send.call_args[0][0]
            assert request["filters"] == filters

    def test_get_status_method(self):
        """Test get_status method."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {
            "status": "running",
            "pid": 12345,
            "uptime": 100,
            "cached_modules": 50
        }

        with patch.object(client, 'send_request', return_value=mock_response) as mock_send:
            response = client.get_status()

            mock_send.assert_called_once_with({"command": "status"})
            assert response == mock_response

    def test_get_health_method(self):
        """Test get_health method."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {
            "status": "healthy",
            "checks": {"socket": True, "memory": True}
        }

        with patch.object(client, 'send_request', return_value=mock_response) as mock_send:
            response = client.get_health()

            mock_send.assert_called_once_with({"command": "health"})
            assert response == mock_response

    def test_reload_method(self):
        """Test reload method sends correct request."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {
            "status": "reloaded",
            "modules_reloaded": 5,
            "reload_time": 0.05
        }

        file_paths = {"/tmp/test1.py", "/tmp/test2.py"}

        with patch.object(client, 'send_request', return_value=mock_response) as mock_send:
            response = client.reload(file_paths)

            mock_send.assert_called_once()
            request = mock_send.call_args[0][0]
            assert request["command"] == "reload"
            assert set(request["file_paths"]) == file_paths

            assert response == mock_response

    def test_reload_method_empty_file_paths(self):
        """Test reload method raises error for empty file_paths."""
        client = DaemonClient("/tmp/test.sock")

        with pytest.raises(ValidationError, match="file_paths cannot be empty"):
            client.reload(set())

    def test_stop_method(self):
        """Test stop method sends correct request."""
        client = DaemonClient("/tmp/test.sock")

        mock_response = {"status": "stopped"}

        with patch.object(client, 'send_request', return_value=mock_response) as mock_send:
            response = client.stop()

            # Should use shorter timeout for stop
            mock_send.assert_called_once_with({"command": "stop"}, timeout=2.0)
            assert response == mock_response


class TestHelperFunctions:
    """Test module-level helper functions."""

    def test_get_socket_path_deterministic(self):
        """Test get_socket_path is deterministic for same path."""
        path1 = get_socket_path("/tmp/project")
        path2 = get_socket_path("/tmp/project")

        assert path1 == path2

    def test_get_socket_path_different_projects(self):
        """Test different projects get different socket paths."""
        path1 = get_socket_path("/tmp/project1")
        path2 = get_socket_path("/tmp/project2")

        assert path1 != path2

    def test_get_socket_path_normalized(self):
        """Test socket path is normalized (relative vs absolute)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory
            subdir = Path(tmpdir) / "project"
            subdir.mkdir()

            # Change to tmpdir and use relative path
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                path1 = get_socket_path("project")
                path2 = get_socket_path(str(subdir))

                # Should be same because paths resolve to same location
                assert path1 == path2
            finally:
                os.chdir(original_cwd)

    def test_get_socket_path_format(self):
        """Test socket path has expected format."""
        socket_path = get_socket_path("/tmp/project")

        assert socket_path.startswith("/tmp/pytest-fastcollect-")
        assert socket_path.endswith(".sock")
        assert len(socket_path.split("-")[-1].replace(".sock", "")) == 8  # 8-char hash

    def test_get_pid_file(self):
        """Test get_pid_file returns correct path."""
        from pytest_fastcollect.daemon_client import get_pid_file

        socket_path = "/tmp/test.sock"
        pid_file = get_pid_file(socket_path)

        assert pid_file == "/tmp/test.sock.pid"

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
            pid_file = get_pid_file(socket_path)
            if os.path.exists(pid_file):
                os.remove(pid_file)
            if os.path.exists(socket_path):
                os.remove(socket_path)

    def test_get_daemon_pid_no_file(self):
        """Test get_daemon_pid returns None when file doesn't exist."""
        pid = get_daemon_pid("/nonexistent.sock")
        assert pid is None

    def test_get_daemon_pid_invalid_content(self):
        """Test get_daemon_pid handles invalid PID content."""
        with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
            socket_path = f.name

        try:
            pid_file = get_pid_file(socket_path)

            # Write invalid PID
            with open(pid_file, 'w') as f:
                f.write("not a number")

            pid = get_daemon_pid(socket_path)
            assert pid is None

        finally:
            # Cleanup
            if os.path.exists(pid_file):
                os.remove(pid_file)
            if os.path.exists(socket_path):
                os.remove(socket_path)

    def test_get_daemon_pid_negative_pid(self):
        """Test get_daemon_pid rejects negative PIDs."""
        with tempfile.NamedTemporaryFile(suffix=".sock", delete=False) as f:
            socket_path = f.name

        try:
            pid_file = get_pid_file(socket_path)

            # Write negative PID
            with open(pid_file, 'w') as f:
                f.write("-123")

            pid = get_daemon_pid(socket_path)
            assert pid is None

        finally:
            # Cleanup
            if os.path.exists(pid_file):
                os.remove(pid_file)
            if os.path.exists(socket_path):
                os.remove(socket_path)

    def test_is_process_running_current_process(self):
        """Test is_process_running returns True for current process."""
        assert is_process_running(os.getpid()) is True

    def test_is_process_running_invalid_pids(self):
        """Test is_process_running returns False for invalid PIDs."""
        assert is_process_running(0) is False
        assert is_process_running(-1) is False
        assert is_process_running(-999) is False

    def test_is_process_running_nonexistent_pid(self):
        """Test is_process_running returns False for non-existent PID."""
        # Use a very high PID that's unlikely to exist
        assert is_process_running(999999) is False


class TestStopDaemon:
    """Test stop_daemon function."""

    def test_stop_daemon_via_socket(self):
        """Test stopping daemon via socket command."""
        socket_path = "/tmp/test.sock"

        with patch('pytest_fastcollect.daemon_client.DaemonClient') as mock_client_class:
            with patch('os.path.exists', return_value=False):
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                result = stop_daemon(socket_path)

                mock_client.stop.assert_called_once()
                assert result is True

    def test_stop_daemon_via_sigterm(self):
        """Test stopping daemon via SIGTERM."""
        socket_path = "/tmp/test.sock"

        with patch('pytest_fastcollect.daemon_client.DaemonClient') as mock_client_class:
            with patch('pytest_fastcollect.daemon_client.get_daemon_pid', return_value=12345):
                with patch('pytest_fastcollect.daemon_client.is_process_running', side_effect=[True, False]):
                    with patch('os.kill') as mock_kill:
                        with patch('os.path.exists', return_value=False):
                            # Socket stop fails
                            mock_client = MagicMock()
                            mock_client.stop.side_effect = ConnectionError("Not running")
                            mock_client_class.return_value = mock_client

                            result = stop_daemon(socket_path)

                            # Should try SIGTERM
                            mock_kill.assert_called_once_with(12345, 15)
                            assert result is True

    def test_stop_daemon_via_sigkill(self):
        """Test stopping daemon via SIGKILL when SIGTERM fails."""
        socket_path = "/tmp/test.sock"

        with patch('pytest_fastcollect.daemon_client.DaemonClient') as mock_client_class:
            with patch('pytest_fastcollect.daemon_client.get_daemon_pid', return_value=12345):
                # Process still running after SIGTERM
                with patch('pytest_fastcollect.daemon_client.is_process_running', return_value=True):
                    with patch('os.kill') as mock_kill:
                        with patch('os.path.exists', return_value=False):
                            # Socket stop fails
                            mock_client = MagicMock()
                            mock_client.stop.side_effect = ConnectionError("Not running")
                            mock_client_class.return_value = mock_client

                            result = stop_daemon(socket_path)

                            # Should try both SIGTERM and SIGKILL
                            assert mock_kill.call_count == 2
                            mock_kill.assert_any_call(12345, 15)  # SIGTERM
                            mock_kill.assert_any_call(12345, 9)   # SIGKILL
                            assert result is True

    def test_stop_daemon_cleanup_stale_files(self):
        """Test stop_daemon cleans up stale socket and PID files."""
        socket_path = "/tmp/test.sock"
        pid_file = "/tmp/test.sock.pid"

        with patch('pytest_fastcollect.daemon_client.DaemonClient') as mock_client_class:
            with patch('pytest_fastcollect.daemon_client.get_daemon_pid', return_value=None):
                with patch('os.path.exists') as mock_exists:
                    with patch('os.remove') as mock_remove:
                        # Socket stop fails, but files exist
                        mock_client = MagicMock()
                        mock_client.stop.side_effect = ConnectionError("Not running")
                        mock_client_class.return_value = mock_client

                        # Both socket and PID file exist
                        mock_exists.side_effect = lambda path: path in [socket_path, pid_file]

                        result = stop_daemon(socket_path)

                        # Should remove both files
                        assert mock_remove.call_count == 2
                        assert result is True

    def test_stop_daemon_not_running(self):
        """Test stop_daemon when daemon is not running."""
        socket_path = "/tmp/test.sock"

        with patch('pytest_fastcollect.daemon_client.DaemonClient') as mock_client_class:
            with patch('pytest_fastcollect.daemon_client.get_daemon_pid', return_value=None):
                with patch('os.path.exists', return_value=False):
                    # Socket stop fails
                    mock_client = MagicMock()
                    mock_client.stop.side_effect = ConnectionError("Not running")
                    mock_client_class.return_value = mock_client

                    result = stop_daemon(socket_path)

                    # Should return False (daemon wasn't running, no cleanup needed)
                    assert result is False


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test exception hierarchy and types."""

    def test_client_error_base_exception(self):
        """Test ClientError is base exception."""
        error = ClientError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_connection_error_inheritance(self):
        """Test ConnectionError inherits from ClientError."""
        error = ConnectionError("Connection failed")
        assert isinstance(error, ClientError)
        assert isinstance(error, Exception)

    def test_timeout_error_inheritance(self):
        """Test TimeoutError inherits from ClientError."""
        error = TimeoutError("Timed out")
        assert isinstance(error, ClientError)
        assert isinstance(error, Exception)

    def test_validation_error_inheritance(self):
        """Test ValidationError inherits from ClientError."""
        error = ValidationError("Invalid request")
        assert isinstance(error, ClientError)
        assert isinstance(error, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
