# Future Implementation: Rust + Ratatui

This document outlines the plan for a more robust, cross-platform implementation using Rust.

## Why Rust?

- **Single binary**: No Python/runtime dependencies, easy to distribute
- **Performance**: Near-instant startup, minimal memory usage
- **Cross-platform**: First-class Windows support
- **ratatui**: Excellent TUI library with rich widget support

## Architecture

### Phase 1: Basic Monitor (File-based, like current Python version)

```
agent-monitor/
├── Cargo.toml
├── src/
│   ├── main.rs           # CLI entry point
│   ├── monitor.rs        # Dashboard logic
│   ├── reporter.rs       # Status reporting
│   ├── status.rs         # Status file handling
│   └── ui/
│       ├── mod.rs
│       ├── dashboard.rs  # Main dashboard widget
│       └── agent_row.rs  # Individual agent display
```

### Phase 2: IPC Communication

#### Cross-Platform Strategy

**Option A: HTTP localhost (Recommended for simplicity)**
- Works identically on all platforms
- Easy to debug (curl, browser)
- Slightly higher overhead but negligible for this use case
- No platform-specific code needed

```rust
// Server (monitor)
use axum::{Router, Json};

async fn receive_status(Json(status): Json<AgentStatus>) -> impl IntoResponse {
    // Update internal state
}

// Client (reporter)  
use reqwest;

async fn report_status(status: &AgentStatus) -> Result<()> {
    reqwest::Client::new()
        .post("http://127.0.0.1:7878/status")
        .json(status)
        .send()
        .await?;
    Ok(())
}
```

**Option B: Platform-specific IPC**

| Platform | IPC Method | Rust Crate |
|----------|------------|------------|
| Linux/macOS | Unix Domain Socket | `tokio::net::UnixListener` |
| Windows | Named Pipe | `tokio::net::windows::named_pipe` |

```rust
// Abstraction layer
#[cfg(unix)]
mod ipc {
    use tokio::net::UnixListener;
    
    pub async fn create_listener() -> impl Stream<Item = Connection> {
        let path = dirs::runtime_dir().unwrap().join("agent-monitor.sock");
        UnixListener::bind(&path).unwrap()
    }
}

#[cfg(windows)]
mod ipc {
    use tokio::net::windows::named_pipe;
    
    pub async fn create_listener() -> impl Stream<Item = Connection> {
        named_pipe::ServerOptions::new()
            .create(r"\\.\pipe\agent-monitor")
            .unwrap()
    }
}
```

**Recommendation**: Start with HTTP localhost. It's simpler, cross-platform out of the box, and the overhead is negligible. Only switch to native IPC if you need sub-millisecond latency (unlikely for this use case).

### Phase 3: Enhanced Features

#### Interactive Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  CLAUDE AGENT MONITOR                        01:23:45 PM    │
│  [q]uit  [r]efresh  [1-9] select  [enter] open  [l]ogs      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ >⏳  1. feature-auth    WAITING FOR INPUT         2m ago    │
│       "Need clarification: should login use OAuth or..."    │
│                                                             │
│  🔄  2. bugfix-api      RUNNING                  30s ago    │
│       "Refactoring error handling in api/routes.ts"         │
│                                                             │
│  ✅  3. feature-ui      IDLE                      5m ago    │
│       "Completed: Added dark mode toggle"                   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ LOGS: feature-auth                                          │
│ > Analyzing authentication requirements...                  │
│ > Found existing OAuth implementation in auth/oauth.ts      │
│ > Question: Should I extend OAuth or add JWT as alternative?│
└─────────────────────────────────────────────────────────────┘
```

Features:
- **Keyboard navigation**: Arrow keys or numbers to select agents
- **Open terminal**: Press Enter to open a new terminal in that worktree
- **Log tailing**: See recent output from the selected agent
- **Send input**: Type responses directly to waiting agents

#### Agent Log Streaming

Agents can stream their output to the monitor for real-time visibility:

```rust
// Reporter side
pub fn log(worktree: &str, message: &str) {
    // Append to ring buffer or stream to monitor
}

// Monitor side
struct AgentState {
    status: Status,
    recent_logs: VecDeque<String>,  // Ring buffer of recent output
}
```

#### Desktop Notifications (Optional)

For users who want them, opt-in notifications when status changes to `waiting_input`:

```rust
#[cfg(feature = "notifications")]
use notify_rust::Notification;

fn notify_waiting(agent: &str, summary: &str) {
    Notification::new()
        .summary(&format!("Agent {} needs input", agent))
        .body(summary)
        .show()
        .ok();
}
```

## Crate Dependencies

```toml
[dependencies]
# TUI
ratatui = "0.26"
crossterm = "0.27"

# Async runtime
tokio = { version = "1", features = ["full"] }

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# HTTP (for IPC)
axum = "0.7"        # server
reqwest = "0.11"    # client

# Utilities
dirs = "5"          # Platform-specific directories
chrono = "0.4"      # Time handling
clap = "4"          # CLI parsing

# Optional
notify-rust = { version = "4", optional = true }

[features]
default = []
notifications = ["notify-rust"]
```

## File Locations (Cross-Platform)

```rust
use dirs;

fn status_dir() -> PathBuf {
    // Linux: ~/.local/share/agent-monitor/status
    // macOS: ~/Library/Application Support/agent-monitor/status  
    // Windows: C:\Users\<user>\AppData\Roaming\agent-monitor\status
    dirs::data_dir()
        .unwrap()
        .join("agent-monitor")
        .join("status")
}

fn socket_path() -> PathBuf {
    // Linux: /run/user/<uid>/agent-monitor.sock
    // macOS: ~/Library/Caches/agent-monitor.sock
    // Windows: \\.\pipe\agent-monitor (named pipe, not a path)
    #[cfg(unix)]
    {
        dirs::runtime_dir()
            .unwrap_or_else(|| dirs::cache_dir().unwrap())
            .join("agent-monitor.sock")
    }
    #[cfg(windows)]
    {
        PathBuf::from(r"\\.\pipe\agent-monitor")
    }
}
```

## Migration Path

1. **v0.1** (Current): Python + rich, file-based
2. **v0.2**: Rust rewrite, file-based, same functionality
3. **v0.3**: Add HTTP IPC for real-time updates
4. **v0.4**: Interactive features (navigation, log viewing)
5. **v0.5**: Optional: Native IPC, notifications

## Development Notes

### Testing Cross-Platform

```bash
# Linux/macOS
cargo build --release
./target/release/agent-monitor

# Windows (cross-compile from Linux)
cargo build --release --target x86_64-pc-windows-gnu

# Or use GitHub Actions for CI on all platforms
```

### Graceful Degradation

The Rust version should:
- Fall back to file-based if IPC fails
- Work without notifications if the feature is disabled
- Handle missing status directory gracefully
- Support both old (Python) and new (Rust) reporters during transition
