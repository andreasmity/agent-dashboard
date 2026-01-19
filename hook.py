#!/usr/bin/env python3
"""
Claude Code Hook Handler - Parses hook events and updates agent monitor status.

This script is called by Claude Code hooks and receives JSON via stdin.

Claude Code Hook Input (via stdin):
    {
        "session_id": "...",
        "transcript_path": "...",
        "cwd": "/current/working/directory",
        "permission_mode": "...",
        "hook_event_name": "PreToolUse" | "PostToolUse" | "Notification" | "Stop" | etc,
        "tool_name": "...",        // for tool-related hooks
        "tool_input": {...},       // for PreToolUse/PostToolUse
        "tool_response": {...},    // for PostToolUse only
        "prompt": "...",           // for UserPromptSubmit
        "message": "...",          // for Notification
        "notification_type": "...", // for Notification
        ...
    }

Environment variables available:
    CLAUDE_PROJECT_DIR - Project root directory (absolute path)

Usage in ~/.claude/settings.json:
    {
      "hooks": {
        "Notification": [
          {
            "matcher": "",
            "hooks": [{ "type": "command", "command": "python /path/to/hook.py" }]
          }
        ],
        "PreToolUse": [
          {
            "matcher": "",
            "hooks": [{ "type": "command", "command": "python /path/to/hook.py" }]
          }
        ],
        "Stop": [
          {
            "matcher": "",
            "hooks": [{ "type": "command", "command": "python /path/to/hook.py" }]
          }
        ]
      }
    }

Or use the /hooks command in Claude Code to configure interactively.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

# Import from report.py (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from report import report_status, clear_status


def get_repo_name_from_git(cwd: str) -> Optional[str]:
    """
    Get repo name from git remote origin URL.
    """
    try:
        # Get repo name from remote origin URL
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract repo name from URL formats:
            # https://github.com/user/repo.git -> repo
            # git@github.com:user/repo.git -> repo
            match = re.search(r'[/:]([^/:]+?)(?:\.git)?$', url)
            if match:
                return match.group(1)
        
        # Fallback: use git root directory name
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
            
    except Exception:
        pass
    
    return None


def get_worktree_name_from_git(cwd: str) -> Optional[str]:
    """
    Get worktree name from git toplevel directory.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).name
    except Exception:
        pass
    
    return Path(cwd).name


def get_identity_from_event(event: dict) -> Tuple[str, str]:
    """
    Extract repo and worktree identity from the hook event.
    
    Uses cwd from event JSON and CLAUDE_PROJECT_DIR env var,
    then runs git commands to get repo/worktree names.
    """
    cwd = event.get("cwd", os.getcwd())
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", cwd)
    
    # Get repo name from git
    repo = get_repo_name_from_git(project_dir) or Path(project_dir).name or "_default"
    
    # Get worktree name from git
    worktree = get_worktree_name_from_git(cwd) or Path(cwd).name or "_default"
    
    return repo, worktree


def handle_notification(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle Notification hook."""
    notification_type = event.get("notification_type", "")
    message = event.get("message", "")
    
    # Determine status based on notification_type (the reliable indicator)
    if notification_type == "permission_prompt":
        status = "waiting_input"
        summary = "Waiting for permission"
    elif notification_type == "idle_prompt":
        status = "waiting_input"
        summary = "Waiting for input"
    elif notification_type == "elicitation_dialog":
        status = "waiting_input"
        summary = "Waiting for MCP input"
    else:
        # Other notifications - agent is running
        status = "running"
        summary = f"Notification: {notification_type}" if notification_type else "Processing"
    
    report_status(worktree=worktree, status=status, summary=summary, repo=repo, path=cwd)


def handle_pre_tool_use(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle PreToolUse hook."""
    tool_name = event.get("tool_name", "unknown")
    tool_input = event.get("tool_input", {})
    
    # Build summary from tool name and input
    summary = f"Using {tool_name}"
    
    if isinstance(tool_input, dict):
        if "command" in tool_input:
            cmd = str(tool_input["command"])[:40]
            summary = f"Running: {cmd}"
        elif "file_path" in tool_input:
            path = Path(str(tool_input["file_path"])).name
            summary = f"{tool_name}: {path}"
        elif "pattern" in tool_input:
            pattern = str(tool_input["pattern"])[:30]
            summary = f"{tool_name}: {pattern}"
    
    report_status(worktree=worktree, status="running", summary=summary, repo=repo, path=cwd)


def handle_post_tool_use(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle PostToolUse hook."""
    tool_name = event.get("tool_name", "unknown")
    tool_response = event.get("tool_response", {})
    
    # Check for errors
    if isinstance(tool_response, dict):
        if tool_response.get("error") or tool_response.get("success") is False:
            error_msg = tool_response.get("error", "Failed")
            report_status(
                worktree=worktree,
                status="error",
                summary=f"{tool_name}: {str(error_msg)[:60]}",
                repo=repo,
                path=cwd,
            )
            return
    
    report_status(worktree=worktree, status="running", summary=f"Completed {tool_name}", repo=repo, path=cwd)


def handle_stop(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle Stop/SubagentStop hook - Claude finished responding."""
    report_status(worktree=worktree, status="idle", summary="Task completed", repo=repo, path=cwd)


def handle_user_prompt_submit(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle UserPromptSubmit hook."""
    prompt = event.get("prompt", "")
    summary = f"Processing: {prompt[:50]}..." if len(prompt) > 50 else f"Processing: {prompt}" if prompt else "Processing prompt"
    report_status(worktree=worktree, status="running", summary=summary, repo=repo, path=cwd)


def handle_session_start(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle SessionStart hook."""
    source = event.get("source", "startup")
    summary_map = {
        "startup": "Session started",
        "resume": "Session resumed", 
        "clear": "Session cleared",
        "compact": "Context compacted",
    }
    report_status(worktree=worktree, status="running", summary=summary_map.get(source, "Session active"), repo=repo, path=cwd)


def handle_session_end(event: dict, repo: str, worktree: str, cwd: str) -> None:
    """Handle SessionEnd hook - clear status since session ended."""
    clear_status(worktree, repo)


def main():
    """Main entry point - reads hook event from stdin and routes to handler."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(0)
        event = json.loads(raw_input)
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(0)
    
    repo, worktree = get_identity_from_event(event)
    cwd = event.get("cwd", os.getcwd())
    hook_type = event.get("hook_event_name", "")
    
    handlers = {
        "Notification": handle_notification,
        "PreToolUse": handle_pre_tool_use,
        "PostToolUse": handle_post_tool_use,
        "Stop": handle_stop,
        "SubagentStop": handle_stop,
        "UserPromptSubmit": handle_user_prompt_submit,
        "SessionStart": handle_session_start,
        "SessionEnd": handle_session_end,
    }
    
    handler = handlers.get(hook_type)
    if handler:
        handler(event, repo, worktree, cwd)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
