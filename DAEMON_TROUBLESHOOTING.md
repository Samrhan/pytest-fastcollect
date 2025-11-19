# Collection Daemon Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Collection Daemon.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
- [Performance Issues](#performance-issues)
- [Debugging](#debugging)
- [Best Practices](#best-practices)
- [Advanced Topics](#advanced-topics)

## Quick Diagnostics

### Check Daemon Status

```bash
# Check if daemon is running
pytest --daemon-status

# Check daemon health
pytest --daemon-health
```

### Check Logs

The daemon writes detailed logs to help diagnose issues:

```bash
# View daemon logs
tail -f /tmp/daemon.log

# Search for errors in logs
grep ERROR /tmp/daemon.log

# Search for warnings
grep WARN /tmp/daemon.log
```

### Verify Socket File

```bash
# Check if socket exists (replace hash with your project's hash)
ls -la /tmp/pytest-fastcollect-*.sock

# Check socket permissions
ls -l /tmp/pytest-fastcollect-*.sock
```

## Common Issues

### 1. Cannot Connect to Daemon

**Symptoms:**
```
ConnectionError: Cannot connect to daemon at /tmp/pytest-fastcollect-xxxxx.sock.
Is the daemon running?
```

**Causes & Solutions:**

#### Daemon Not Running
```bash
# Check if daemon is running
pytest --daemon-status

# If not running, start it
pytest --daemon-start tests/
```

#### Stale Socket File
```bash
# Stop daemon (cleans up stale files)
pytest --daemon-stop

# Restart daemon
pytest --daemon-start tests/
```

#### Permission Issues
```bash
# Check socket permissions
ls -l /tmp/pytest-fastcollect-*.sock

# Should show: srw-rw-rw- (socket, read-write for all)
# If not, stop and restart daemon
pytest --daemon-stop
pytest --daemon-start tests/
```

### 2. Daemon Fails to Start

**Symptoms:**
```
DaemonError: Cannot create socket: Address already in use
```

**Solutions:**

#### Port/Socket Already in Use
```bash
# Stop existing daemon
pytest --daemon-stop

# If that doesn't work, find and kill process
ps aux | grep pytest-fastcollect
kill <PID>

# Remove stale socket
rm /tmp/pytest-fastcollect-*.sock*

# Restart daemon
pytest --daemon-start tests/
```

#### Insufficient Permissions
```bash
# Check /tmp directory permissions
ls -ld /tmp

# Ensure you have write access
touch /tmp/test-write && rm /tmp/test-write
```

### 3. Import Failures

**Symptoms:**
```
Daemon: Imported 50/100 modules in 5.23s
```

**Causes & Solutions:**

#### Missing Dependencies
```bash
# Check daemon logs for import errors
grep "Failed to import" /tmp/daemon.log

# Install missing dependencies
pip install <missing-package>

# Reload daemon
pytest --daemon-stop
pytest --daemon-start tests/
```

#### Syntax Errors in Test Files
```bash
# Check logs for syntax errors
grep "SyntaxError" /tmp/daemon.log

# Fix the problematic files
# Then reload daemon
pytest --daemon-stop
pytest --daemon-start tests/
```

#### Circular Import Issues
```bash
# Identify circular imports in logs
grep "ImportError" /tmp/daemon.log

# Refactor code to remove circular imports
# Reload daemon
pytest --daemon-stop
pytest --daemon-start tests/
```

### 4. Stale Module Cache

**Symptoms:**
- Tests fail unexpectedly
- Code changes not reflected
- Old test results

**Solutions:**

```bash
# Reload daemon to refresh modules
pytest --daemon-stop
pytest --daemon-start tests/

# Or force reload (future feature)
# pytest --daemon-reload
```

### 5. Memory Issues

**Symptoms:**
- Daemon consuming excessive memory
- System slowdown
- Out of memory errors

**Solutions:**

```bash
# Check daemon memory usage
ps aux | grep pytest-fastcollect

# Stop daemon to free memory
pytest --daemon-stop

# For large projects, consider:
# 1. Increasing system memory
# 2. Running daemon only when needed
# 3. Using selective test execution
```

## Performance Issues

### Slow Import Times

**Diagnosis:**
```bash
# Check daemon startup logs
grep "Pre-import complete" /tmp/daemon.log

# Example output:
# Pre-import complete: 95/100 modules in 12.45s
```

**Optimization:**

1. **Reduce Import Overhead:**
   - Remove unnecessary imports from test files
   - Use lazy imports where possible
   - Avoid importing heavy dependencies at module level

2. **Selective Testing:**
   - Use `-k` filter to run specific tests
   - Use `-m` markers to run tagged tests
   - Daemon only helps when modules are already imported

### High Connection Latency

**Diagnosis:**
```bash
# Check request times in logs
grep "Request.*completed" /tmp/daemon.log

# Example output:
# Request [12345-1234567890.12] completed in 0.0015s: success
```

**Solutions:**

- Ensure daemon is running on local filesystem (not network mount)
- Check system load (`top`, `htop`)
- Restart daemon if it's been running for very long

## Debugging

### Enable Debug Logging

The daemon uses Python's logging module. To get more detailed logs:

```python
# In your test setup or conftest.py
import logging
logging.getLogger('pytest_fastcollect.daemon').setLevel(logging.DEBUG)
logging.getLogger('pytest_fastcollect.daemon_client').setLevel(logging.DEBUG)
```

### Trace Daemon Communication

```bash
# Watch daemon logs in real-time
tail -f /tmp/daemon.log | grep -E "(Processing request|Request.*completed)"
```

### Check System Resources

```bash
# CPU and memory usage
top -p $(pgrep -f pytest-fastcollect)

# Open file descriptors
lsof -p $(pgrep -f pytest-fastcollect)

# Network/socket connections
ss -x | grep pytest-fastcollect
```

### Manual Testing

Test daemon communication manually:

```python
from pytest_fastcollect.daemon_client import DaemonClient, get_socket_path

# Get socket path for your project
socket_path = get_socket_path("/path/to/your/project")

# Create client
client = DaemonClient(socket_path)

# Test connection
if client.is_daemon_running():
    print("Daemon is running!")

    # Get status
    status = client.get_status()
    print(f"Status: {status}")

    # Get health
    health = client.get_health()
    print(f"Health: {health}")
else:
    print("Daemon is not running")
```

## Best Practices

### 1. Regular Restarts

For long-running development sessions, restart the daemon periodically:

```bash
# Every few hours or after major code changes
pytest --daemon-stop
pytest --daemon-start tests/
```

### 2. Clean Shutdown

Always stop the daemon cleanly when done:

```bash
# Before logging out or shutting down
pytest --daemon-stop

# Or in scripts
trap "pytest --daemon-stop" EXIT
```

### 3. Monitor Health

Regularly check daemon health:

```bash
# Add to your dev workflow
pytest --daemon-health

# Example healthy output:
# Status: healthy
# Checks:
#   - socket_alive: True
#   - running: True
#   - request_error_rate: 0.02 (2%)
```

### 4. Log Rotation

Daemon logs automatically rotate (10MB max, 5 backups), but you can clean up old logs:

```bash
# Remove old daemon logs
rm /tmp/daemon.log.*
```

### 5. Project Isolation

Each project gets its own daemon:

```bash
# Project 1
cd /path/to/project1
pytest --daemon-start tests/

# Project 2
cd /path/to/project2
pytest --daemon-start tests/

# Both run independently!
```

## Advanced Topics

### Multiple Daemon Instances

Run daemons for multiple projects simultaneously:

```bash
# Terminal 1: Project A
cd /path/to/project-a
pytest --daemon-start tests/
pytest --daemon-status  # Shows project A daemon

# Terminal 2: Project B
cd /path/to/project-b
pytest --daemon-start tests/
pytest --daemon-status  # Shows project B daemon
```

### Security Considerations

The daemon implements several security measures:

1. **Path Validation:**
   - Only imports files within project root
   - Prevents directory traversal attacks

2. **Input Validation:**
   - Validates all requests before processing
   - Rejects malformed or oversized requests

3. **Resource Limits:**
   - Maximum 10 concurrent connections
   - Maximum 10MB request size
   - 30-second request timeout

4. **Socket Permissions:**
   - Socket file has 0666 permissions (read-write for all)
   - Safe for multi-user systems
   - Per-project isolation via unique socket paths

### Programmatic Usage

Use the daemon API in your own scripts:

```python
from pytest_fastcollect.daemon_client import (
    DaemonClient,
    get_socket_path,
    stop_daemon
)

# Get socket for current project
socket_path = get_socket_path(".")

# Create client
client = DaemonClient(socket_path)

# Check if running
if not client.is_daemon_running():
    print("Daemon not running, start it with: pytest --daemon-start tests/")
    exit(1)

# Request collection
response = client.collect(".", filters={"-k": "test_user"})
print(f"Collection took {response['collection_time']}s")

# Get metrics
status = client.get_status()
metrics = status['metrics']
print(f"Total requests: {metrics['total_requests']}")
print(f"Success rate: {metrics['successful_requests'] / metrics['total_requests'] * 100}%")

# Stop when done
stop_daemon(socket_path)
```

### Troubleshooting Performance

If the daemon isn't providing expected speedup:

1. **Profile Import Times:**
   ```bash
   python -X importtime -c "import your_test_module" 2>&1 | grep your_test
   ```

2. **Check Cache Hit Rate:**
   ```python
   status = client.get_status()
   cached = status['cached_modules']
   print(f"Cached modules: {cached}")
   ```

3. **Measure Request Time:**
   ```bash
   time pytest --daemon-status
   # Should be very fast (<0.1s)
   ```

## Getting Help

If you're still experiencing issues:

1. **Check daemon logs:**
   ```bash
   cat /tmp/daemon.log
   ```

2. **Collect diagnostic information:**
   ```bash
   pytest --daemon-status
   pytest --daemon-health
   ps aux | grep pytest-fastcollect
   ```

3. **Report issues on GitHub:**
   - Include daemon logs
   - Include output of `--daemon-status` and `--daemon-health`
   - Include Python and pytest versions
   - Describe your project structure and size

4. **Community Support:**
   - Open an issue: https://github.com/yourusername/pytest-fastcollect/issues
   - Provide reproduction steps
   - Share relevant configuration

## Summary

The Collection Daemon is production-ready with:
- ✅ Comprehensive error handling
- ✅ Detailed logging
- ✅ Health monitoring
- ✅ Security features
- ✅ Resource management

Most issues can be resolved by:
1. Checking daemon status and health
2. Reviewing logs for errors
3. Restarting the daemon
4. Following best practices

For persistent issues, the detailed logs and monitoring features help diagnose problems quickly.
