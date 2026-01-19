#!/usr/bin/env python3
"""
Claude Code Hook Handler - Fast, lightweight status updater.

This script reads JSON from stdin and writes status to ~/.agent-monitor/status/
Reads repo/worktree identity from .claude/agent-monitor/config.json for speed.

Claude Code Hook Input (via stdin):
    {
        "session_id": "...",
        "cwd": "/current/working/directory",
        "hook_event_name": "PreToolUse" | "PostToolUse" | "Notification" | "Stop" | etc,
        "tool_name": "...",
        "notification_type": "...",
        ...
    }

Environment variables:
    CLAUDE_PROJECT_DIR - Project root directory (provided by Claude Code)

Config file (.claude/agent-monitor/config.json):
    {
        "repo": "my-repo",
        "worktree": "feature-branch"
    }
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Status directory: ~/.agent-monitor/status/
STATUS_DIR = Path.home() / ".agent-monitor" / "status"


def read_identity_config(project_dir: str) -> tuple[str, str]:
    """
    Read repo and worktree identity from .claude/agent-monitor/config.json

    Returns: (repo, worktree)
    Falls back to session-based if config doesn't exist.
    """
    try:
        config_path = Path(project_dir) / ".claude" / "agent-monitor" / "config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
                repo = config.get("repo", "unknown")
                worktree = config.get("worktree", "unknown")
                return repo, worktree
    except Exception:
        pass

    # Fallback: derive from directory name
    try:
        worktree = Path(project_dir).name
        return "unknown", worktree
    except Exception:
        return "unknown", "unknown"


def write_status(session_id: str, status: str, summary: str, cwd: str = "") -> None:
    """
    Write status file to ~/.agent-monitor/status/<repo>/<worktree>.json

    Reads identity from config file for speed.
    """
    # Get project directory from environment
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", cwd)

    # Read repo and worktree from config
    repo, worktree = read_identity_config(project_dir)

    # Create repo subdirectory
    repo_dir = STATUS_DIR / repo
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Write to <repo>/<worktree>.json
    status_file = repo_dir / f"{worktree}.json"

    # Write status JSON with all required fields
    data = {
        "session_id": session_id,
        "repo": repo,
        "worktree": worktree,
        "status": status,
        "summary": summary,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "path": cwd,
    }

    # Atomic write: write to temp file then rename
    temp_file = status_file.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(data, f)
    temp_file.replace(status_file)


def clear_status(session_id: str, cwd: str = "") -> None:
    """Remove status file for session."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", cwd)
    repo, worktree = read_identity_config(project_dir)

    repo_dir = STATUS_DIR / repo
    status_file = repo_dir / f"{worktree}.json"

    if status_file.exists():
        status_file.unlink()


def determine_status(event: dict) -> tuple[str, str]:
    """
    Determine status and summary from hook event.

    Returns: (status, summary)
    """
    hook_type = event.get("hook_event_name", "")

    # Notification events
    if hook_type == "Notification":
        notification_type = event.get("notification_type", "")
        if notification_type in ("permission_prompt", "idle_prompt", "elicitation_dialog"):
            return "waiting_input", "Waiting for input"
        return "running", "Processing"

    # Tool use events
    if hook_type == "PreToolUse":
        tool_name = event.get("tool_name", "tool")
        return "running", f"Using {tool_name}"

    if hook_type == "PostToolUse":
        tool_name = event.get("tool_name", "tool")
        tool_response = event.get("tool_response", {})
        if isinstance(tool_response, dict) and (tool_response.get("error") or tool_response.get("success") is False):
            return "error", f"{tool_name} failed"
        return "running", f"Completed {tool_name}"

    # Stop events
    if hook_type in ("Stop", "SubagentStop"):
        return "idle", "Task completed"

    # Session events
    if hook_type == "SessionStart":
        return "running", "Session started"

    if hook_type == "SessionEnd":
        return None, None  # Signal to clear

    if hook_type == "UserPromptSubmit":
        prompt = event.get("prompt", "")
        if prompt:
            summary = prompt[:50] + "..." if len(prompt) > 50 else prompt
        else:
            summary = "Processing prompt"
        return "running", summary

    # Default
    return "running", "Active"


def main():
    """Main entry point - reads JSON from stdin and writes status file."""
    try:
        # Read JSON from stdin
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        # Invalid or empty JSON - exit silently
        sys.exit(0)
    except Exception:
        # Any other error - exit silently
        sys.exit(0)

    # Get session_id and cwd
    session_id = event.get("session_id", "")
    if not session_id:
        sys.exit(0)

    cwd = event.get("cwd", "")

    # Determine status
    status, summary = determine_status(event)

    # Handle SessionEnd (clear status)
    if status is None:
        clear_status(session_id, cwd)
    else:
        # Write status file
        write_status(session_id, status, summary, cwd)

    # Exit immediately
    sys.exit(0)


if __name__ == "__main__":
    main()
