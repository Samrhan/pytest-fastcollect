# Collection Daemon: Implementation Plan

## Vision

A long-running background process that keeps test modules imported in memory, serving **instant** collection requests. This provides 100-1000x speedup on subsequent test runs - perfect for development workflows.

## Architecture

### Components

1. **Daemon Process** (`daemon.py`)
   - Long-running Python process
   - Imports all test modules once (cold start)
   - Keeps modules in `sys.modules` (stays in memory)
   - Listens for collection requests via Unix socket
   - Returns serialized collection results instantly

2. **Client Integration** (`plugin.py`)
   - Checks if daemon is running
   - If running: Request collection from daemon (instant!)
   - If not: Fall back to normal collection
   - Handle daemon communication errors gracefully

3. **File Watcher** (Phase 2)
   - Monitor test files for changes using `watchdog`
   - Re-import only changed modules
   - Keep cache hot between runs

### Communication Protocol

**Unix Domain Socket** (fast, local IPC):
```python
# Client → Daemon
{
    "command": "collect",
    "root_path": "/path/to/project",
    "filters": {
        "keyword": "test_user",
        "marker": "smoke"
    }
}

# Daemon → Client
{
    "status": "success",
    "collection_time": 0.001,  # Nearly instant!
    "data": {
        "file1.py": [{"name": "test_foo", ...}],
        ...
    }
}
```

## Implementation Phases

### Phase 1: Basic Daemon (Minimum Viable Product)

**Goal**: Get instant collection working

**Files to create**:
1. `pytest_fastcollect/daemon.py`
   - DaemonServer class
   - Socket listener
   - Request handler
   - Module cache management

2. `pytest_fastcollect/daemon_client.py`
   - DaemonClient class
   - Socket communication
   - Request/response protocol
   - Error handling

3. Update `plugin.py`
   - Add `--daemon-start`, `--daemon-stop`, `--daemon-status` flags
   - Check daemon availability
   - Fall back to normal collection

**Commands**:
```bash
# Start daemon (imports all modules, stays running)
pytest --daemon-start

# Normal pytest run (uses daemon if available)
pytest  # Instant collection!

# Stop daemon
pytest --daemon-stop

# Check status
pytest --daemon-status
```

### Phase 2: File Watching

**Goal**: Auto-detect changes, re-import only changed files

**Additional dependencies**:
- `watchdog`: File system monitoring

**Implementation**:
- Daemon monitors test directories
- Detects file changes (modify, create, delete)
- Re-imports only changed modules
- Invalidates cached collection data

### Phase 3: Advanced Features

- **Multiple projects**: Separate daemon per project root
- **Memory management**: Limit memory usage, evict old modules
- **Watch mode**: `pytest --daemon-watch` continuously monitors
- **Distributed**: Daemon on remote machine (for large projects)

## Expected Performance

### Baseline (no daemon)
```
Cold collection: 10.0s (Django-sized project)
```

### With Collection Daemon
```
First run (daemon start): 10.0s (cold start, import all)
Second run:               0.01s (instant! modules in memory)
Third run:                0.01s (instant!)
...
Speedup: 1000x!
```

### With File Watching
```
First run:                10.0s (cold start)
Change 1 file:            0.1s  (re-import 1 module)
Change 10 files:          1.0s  (re-import 10 modules)
No changes:               0.01s (instant!)
```

## Technical Challenges

### 1. Module State Pollution

**Problem**: Test modules might have side effects
```python
# test_foo.py
some_global = []  # Shared state!

def test_bar():
    some_global.append(1)  # Pollution between runs!
```

**Solution**:
- Document that daemon assumes stateless tests
- Provide `--daemon-reload` to force full reload
- Detect common pollution patterns and warn

### 2. Socket Management

**Problem**: Socket files, permissions, cleanup

**Solution**:
- Use `/tmp/pytest-fastcollect-{project_hash}.sock`
- Clean up on daemon stop
- Handle stale socket files

### 3. Daemon Crashes

**Problem**: Daemon dies, client confused

**Solution**:
- Client detects dead daemon (connection refused)
- Automatic fallback to normal collection
- Clean restart mechanism

### 4. Memory Usage

**Problem**: All modules in memory = high RAM usage

**Solution**:
- Monitor memory, evict old modules if needed
- Provide `--daemon-max-memory` flag
- Show memory stats in `--daemon-status`

## API Design

### Daemon Commands

```python
# Start daemon (background process)
pytest --daemon-start
# Output: "Daemon started (PID 12345)"

# Check if running
pytest --daemon-status
# Output: "Daemon running (PID 12345, 1.2GB RAM, 500 modules cached)"

# Stop daemon
pytest --daemon-stop
# Output: "Daemon stopped"

# Force reload all modules
pytest --daemon-reload
# Output: "Daemon reloaded (500 modules re-imported)"
```

### Normal Usage

```bash
# Just run pytest - uses daemon if available!
pytest

# If daemon running:
# "Using collection daemon (0.01s collection)"

# If daemon not running:
# Falls back to normal collection
```

## Development Workflow

### Perfect for TDD

```bash
# Day 1: Start daemon once
pytest --daemon-start

# Write test
vim test_foo.py

# Run test (instant!)
pytest test_foo.py  # 0.01s

# Fix code
vim foo.py

# Re-run (instant!)
pytest test_foo.py  # 0.01s

# Repeat 100 times...
# Total time saved: 100 * 10s = 1000s = 16 minutes!
```

### Watch Mode

```bash
# Start daemon in watch mode
pytest --daemon-watch

# Monitors files, re-runs tests on change
# Like pytest-watch but with instant collection!
```

## Rollout Strategy

### Phase 1: MVP (Week 1)
- Basic daemon (start/stop/status)
- Socket communication
- Instant collection (no file watching)
- **Goal**: Prove 100x+ speedup

### Phase 2: File Watching (Week 2)
- Add `watchdog` dependency
- Detect file changes
- Re-import only changed modules
- **Goal**: Keep cache hot

### Phase 3: Polish (Week 3)
- Memory management
- Better error handling
- Multiple project support
- **Goal**: Production-ready

## Success Metrics

**Must have**:
- ✅ 100x+ speedup on subsequent runs
- ✅ Stable (doesn't crash)
- ✅ Automatic fallback if daemon not available
- ✅ Works on Linux/macOS (Unix sockets)

**Nice to have**:
- ⚡ File watching (auto re-import)
- ⚡ Multiple project support
- ⚡ Memory management
- ⚡ Windows support (named pipes)

## Code Structure

```
pytest_fastcollect/
├── daemon.py           # Daemon server implementation
├── daemon_client.py    # Client communication
├── daemon_protocol.py  # Request/response protocol
├── plugin.py          # pytest plugin (updated)
└── __init__.py        # Package init

scripts/
└── pytest-daemon      # CLI tool for daemon management
```

## Next Steps

1. ✅ Create this plan document
2. ⏭️ Implement `daemon.py` (basic server)
3. ⏭️ Implement `daemon_client.py` (client communication)
4. ⏭️ Update `plugin.py` (daemon integration)
5. ⏭️ Test on sample project
6. ⏭️ Benchmark on real projects
7. ⏭️ Add file watching (Phase 2)

## References

- Unix Domain Sockets: https://docs.python.org/3/library/socket.html#socket-families
- watchdog: https://python-watchdog.readthedocs.io/
- pytest-watch: https://github.com/joeyespo/pytest-watch (inspiration)

---

**This could be the KILLER feature for pytest-fastcollect!**

100-1000x speedup on subsequent runs = Revolutionary for TDD workflows.
