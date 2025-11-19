"""Constants for pytest-fastcollect.

This module centralizes magic numbers and configuration values to improve
code maintainability and make it easier to tune performance.
"""

# === Daemon Configuration ===

# Maximum size for incoming requests (10MB)
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024

# Maximum number of concurrent client connections
MAX_CONCURRENT_CONNECTIONS = 10

# Socket accept timeout in seconds
SOCKET_ACCEPT_TIMEOUT_SECONDS = 1.0

# Maximum time to process a single request
REQUEST_TIMEOUT_SECONDS = 30.0

# Interval for daemon health checks
HEALTH_CHECK_INTERVAL_SECONDS = 60.0

# Log file rotation settings
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_FILE_BACKUP_COUNT = 5

# Brief pause to prevent tight loops in daemon
DAEMON_LOOP_PAUSE_SECONDS = 0.1


# === Client Configuration ===

# Default number of retry attempts for failed requests
DEFAULT_MAX_RETRIES = 3

# Default timeout for client requests
DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0

# Timeout for health check requests
HEALTH_CHECK_TIMEOUT_SECONDS = 1.0

# Number of retries for health checks
HEALTH_CHECK_RETRIES = 1

# Timeout for stop command
STOP_COMMAND_TIMEOUT_SECONDS = 2.0

# Base sleep time for exponential backoff (in seconds)
RETRY_BACKOFF_BASE_SECONDS = 0.1


# === Process Management ===

# Sleep time after sending stop command
STOP_COMMAND_SLEEP_SECONDS = 0.5

# Sleep time after SIGTERM before checking if process stopped
SIGTERM_WAIT_SECONDS = 0.5

# Sleep time after SIGKILL
SIGKILL_WAIT_SECONDS = 0.2

# Timeout for Windows tasklist command
TASKLIST_TIMEOUT_SECONDS = 5


# === Performance ===

# Fallback CPU count if os.cpu_count() returns None
DEFAULT_CPU_COUNT = 4

# Benchmark timeout for standard pytest collection
BENCHMARK_TIMEOUT_SECONDS = 120


# === Cache Configuration ===

# Cache version string
CACHE_VERSION = "1.0"

# Tolerance for file modification time comparison (in seconds)
MTIME_TOLERANCE_SECONDS = 0.01


# === Socket Path ===

# MD5 hash length for socket path generation
SOCKET_PATH_HASH_LENGTH = 8
