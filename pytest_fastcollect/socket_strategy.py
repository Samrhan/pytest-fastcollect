"""
Socket Strategy: Abstract socket communication for cross-platform support.

Provides clean abstractions for Unix domain sockets and TCP sockets,
enabling seamless cross-platform operation without polluting daemon code.
"""

import os
import socket
from abc import ABC, abstractmethod
from typing import Tuple, Any
import logging

logger = logging.getLogger('pytest_fastcollect.socket_strategy')


class SocketStrategy(ABC):
    """Abstract base class for socket communication strategies."""

    @abstractmethod
    def create_server_socket(self) -> socket.socket:
        """Create and bind a server socket.

        Returns:
            Bound socket ready to listen
        """
        pass

    @abstractmethod
    def create_client_socket(self, timeout: float) -> socket.socket:
        """Create a client socket and connect.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            Connected socket
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up any resources (files, sockets, etc.)."""
        pass

    @abstractmethod
    def get_connection_info(self) -> str:
        """Get human-readable connection information.

        Returns:
            String describing how to connect (e.g., path or host:port)
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if connection information is available for clients.

        Returns:
            True if clients can connect, False otherwise
        """
        pass


class UnixSocketStrategy(SocketStrategy):
    """Unix domain socket strategy (Linux, macOS)."""

    def __init__(self, socket_path: str):
        """Initialize Unix socket strategy.

        Args:
            socket_path: Path to Unix domain socket file
        """
        self.socket_path = socket_path
        self.socket = None
        logger.info(f"Using Unix domain socket strategy: {socket_path}")

    def create_server_socket(self) -> socket.socket:
        """Create and bind Unix domain socket."""
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.socket_path)

        # Make socket accessible (read/write for all users)
        try:
            os.chmod(self.socket_path, 0o666)
        except Exception as e:
            logger.warning(f"Failed to set socket permissions: {e}")

        logger.info(f"Unix socket bound to {self.socket_path}")
        return self.socket

    def create_client_socket(self, timeout: float) -> socket.socket:
        """Create and connect Unix domain socket client."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(self.socket_path)
        logger.debug(f"Connected to Unix socket at {self.socket_path}")
        return sock

    def cleanup(self):
        """Remove Unix socket file."""
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
                logger.debug(f"Removed socket file: {self.socket_path}")
            except Exception as e:
                logger.error(f"Error removing socket file: {e}")

    def get_connection_info(self) -> str:
        """Get socket path."""
        return f"Unix socket: {self.socket_path}"

    def is_available(self) -> bool:
        """Check if socket file exists."""
        return os.path.exists(self.socket_path)


class TcpSocketStrategy(SocketStrategy):
    """TCP socket strategy (Windows, cross-platform fallback)."""

    def __init__(self, base_path: str):
        """Initialize TCP socket strategy.

        Args:
            base_path: Base path for storing port file
        """
        self.base_path = base_path
        self.port_file = base_path + ".port"
        self.port = None
        self.socket = None
        logger.info("Using TCP socket strategy (localhost)")

    def create_server_socket(self) -> socket.socket:
        """Create and bind TCP socket on localhost."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to localhost with automatic port selection
        self.socket.bind(('127.0.0.1', 0))
        self.port = self.socket.getsockname()[1]

        # Save port to file for client discovery
        try:
            with open(self.port_file, 'w') as f:
                f.write(str(self.port))
            logger.info(f"TCP socket bound to 127.0.0.1:{self.port}")
        except Exception as e:
            logger.error(f"Failed to write port file: {e}")
            raise

        return self.socket

    def create_client_socket(self, timeout: float) -> socket.socket:
        """Create and connect TCP socket client."""
        # Read port from file if not already known
        if self.port is None:
            self._read_port()

        if self.port is None:
            raise ConnectionError("TCP port not available. Is daemon running?")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(('127.0.0.1', self.port))
        logger.debug(f"Connected to TCP socket at 127.0.0.1:{self.port}")
        return sock

    def _read_port(self):
        """Read port number from port file."""
        if os.path.exists(self.port_file):
            try:
                with open(self.port_file, 'r') as f:
                    self.port = int(f.read().strip())
                logger.debug(f"Read port {self.port} from {self.port_file}")
            except Exception as e:
                logger.warning(f"Failed to read port file: {e}")

    def cleanup(self):
        """Remove port file."""
        if os.path.exists(self.port_file):
            try:
                os.remove(self.port_file)
                logger.debug(f"Removed port file: {self.port_file}")
            except Exception as e:
                logger.error(f"Error removing port file: {e}")

    def get_connection_info(self) -> str:
        """Get TCP connection info."""
        if self.port is None:
            self._read_port()
        return f"TCP socket: 127.0.0.1:{self.port}" if self.port else "TCP socket: port unknown"

    def is_available(self) -> bool:
        """Check if port file exists and is readable."""
        if self.port is not None:
            return True
        self._read_port()
        return self.port is not None


def create_socket_strategy(socket_path: str) -> SocketStrategy:
    """Factory function to create appropriate socket strategy.

    Args:
        socket_path: Base path for socket (file path or identifier)

    Returns:
        SocketStrategy instance (Unix or TCP based on platform)
    """
    # Check if Unix sockets are available
    has_unix_sockets = hasattr(socket, 'AF_UNIX')

    if has_unix_sockets:
        return UnixSocketStrategy(socket_path)
    else:
        return TcpSocketStrategy(socket_path)
