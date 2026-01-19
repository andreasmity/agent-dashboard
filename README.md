# Agent Monitor

A terminal-centric dashboard for monitoring Claude Code agents running across multiple repositories and git worktrees.

```
╭─  agent-monitor  18:23:45───────────────────────────────────────────────────╮
│                                                                              │
│   webapp  1w 1r                                                             │
│      feature-auth       WAITING       2m   Should I use OAuth or JWT?       │
│      bugfix-api         RUNNING      30s   Refactoring error handling       │
│      feature-ui         IDLE          5m   Completed dark mode toggle       │
│                                                                              │
│   backend-services  1w 1e                                                   │
│      refactor-db        WAITING       8m   Migrate existing data?           │
│      hotfix-login       ERROR         1m   Build failed: missing module     │
│                                                                              │
│   ml-pipeline                                                               │
│      experiment-bert    RUNNING      10s   Training: epoch 42/100           │
│      data-cleaning      IDLE         15m   Completed preprocessing          │
│                                                                              │
╰────────────────────────────────────────────2 waiting | 2 running | 7 total──╯
```

**Requires:** [Nerd Font](https://www.nerdfonts.com/) (e.g., CascadiaCode Nerd Font) for icons

## Installation

```bash
# Clone and install
git clone https://github.com/yourusername/agent-monitor
cd agent-monitor
pip install -e .

# Or just install dependencies and run directly
pip install rich
python monitor.py
```

## Quick Start

```bash
# 1. Run the dashboard (in a dedicated terminal)
agent-monitor

# 2. In another terminal, test with demo data
python demo.py

# 3. Configure Claude Code hooks (see below)
```

## Claude Code Integration

### Setting Up Global Hooks

Add hooks to your **global** Claude settings at `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/agent-monitor/hook.py"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/agent-monitor/hook.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python /path/to/agent-monitor/hook.py"
          }
        ]
      }
    ]
  }
}
```

**Important notes:**
- Replace `/path/to/agent-monitor` with your actual installation path
- On Windows, use forward slashes or escaped backslashes in the path
- The hook names are `Notification`, `PreToolUse`, `Stop` (not `NotificationHook`, etc.)
- Use the `/hooks` command in Claude Code to configure hooks interactively (recommended)

### Auto-Detection

The hook automatically detects:
- **Repo name**: From `git remote origin` URL, falling back to git root directory name
- **Worktree name**: From the current directory name (which typically includes the branch for worktrees)

You can override with environment variables:
- `AGENT_REPO`: Override repo name
- `AGENT_WORKTREE`: Override worktree name

### Global Instructions for Agents

Claude Code supports a **global CLAUDE.md** file that applies to all projects. Copy the agent instructions there:

```bash
# Copy to global location (applies to ALL projects)
cp /path/to/agent-monitor/CLAUDE.md ~/.claude/CLAUDE.md

# Or append if you already have a global CLAUDE.md
cat /path/to/agent-monitor/CLAUDE.md >> ~/.claude/CLAUDE.md
```

This teaches all Claude Code agents to use explicit status tags:

```
[STATUS: Waiting for decision on authentication approach]

I've analyzed two options:
1. OAuth 2.0 - better for external integrations  
2. JWT - simpler implementation

Which would you prefer?
```

The monitor extracts `[STATUS: ...]` tags for the summary column, and also auto-detects questions and tool usage.

## Status Directory Structure

Status files are organized by repo:

```
~/.agent-monitor/status/
├── webapp/
│   ├── feature-auth.json
│   ├── bugfix-api.json
│   └── feature-ui.json
├── backend-services/
│   ├── refactor-db.json
│   └── hotfix-login.json
└── ml-pipeline/
    ├── experiment-bert.json
    └── data-cleaning.json
```

## Usage

### Dashboard Commands

```bash
# Run live dashboard (Ctrl+C to exit)
agent-monitor

# Print once and exit (for scripting)
agent-monitor --once

# Custom refresh rate (default: 1 second)
agent-monitor --refresh 0.5

# Custom status directory
agent-monitor --status-dir /custom/path
```

### Manual Status Reporting

For testing or non-Claude-Code agents:

```bash
# Report status with repo
agent-report webapp feature-auth running "Refactoring auth module"
agent-report webapp feature-auth waiting_input "OAuth or JWT?"
agent-report backend hotfix-login error "Build failed"

# Report status without repo (uses _default)
agent-report my-worktree running "Working on feature"

# Clear an agent's status
agent-report webapp feature-auth --clear
```

### Programmatic Usage

```python
from agent_monitor import report_status, clear_status

report_status(
    repo="webapp",
    worktree="feature-auth",
    status="waiting_input",
    summary="Should I use OAuth or JWT?",
    path="/path/to/worktree"
)

clear_status("feature-auth", repo="webapp")
```

## Status Types

| Status | Icon | Description |
|--------|------|-------------|
| `running` | 󰓦 | Agent is actively working |
| `waiting_input` |  | Agent needs user input |
| `idle` |  | Agent completed its task |
| `error` |  | Agent encountered an error |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_MONITOR_DIR` | Status file directory | `~/.agent-monitor/status` |
| `AGENT_REPO` | Override repo name | auto-detected |
| `AGENT_WORKTREE` | Override worktree name | auto-detected |

### Status File Format

```json
{
  "repo": "webapp",
  "worktree": "feature-auth",
  "status": "waiting_input",
  "summary": "Should I use OAuth or JWT?",
  "path": "/home/user/webapp-feature-auth",
  "updated_at": "2025-01-18T13:21:00+00:00"
}
```

## Project Structure

```
agent-monitor/
├── monitor.py      # Dashboard TUI
├── report.py       # CLI status reporter
├── hook.py         # Claude Code hook handler
├── demo.py         # Generate test data
├── CLAUDE.md       # Instructions for Claude agents (copy to ~/.claude/)
├── FUTURE.md       # Roadmap (Rust rewrite)
└── src/agent_monitor/  # Installable package
```

## Tips

### Dedicated Monitor Terminal

Keep a terminal open just for the monitor. With tmux or a tiled terminal:

```bash
# In a dedicated pane/tab
agent-monitor
```

### Quick Status Check

Use `--once` for a quick glance without entering the live view:

```bash
agent-monitor --once
```

## Future Plans

See `FUTURE.md` for the roadmap:
- Rust + ratatui rewrite for single-binary distribution
- Cross-platform IPC (HTTP localhost for simplicity)
- Interactive features (keyboard nav, jump to worktree)
- Log tailing for selected agents
- Optional desktop notifications

## License

MIT
