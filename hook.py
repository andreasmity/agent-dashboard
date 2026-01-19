#!/usr/bin/env python3
"""
Claude Code Hook Handler - Parses hook events and updates agent monitor status.

This script is called by Claude Code hooks and parses the JSON event from stdin.

Usage in ~/.claude/settings.json (global hooks):
    {
      "hooks": {
        "NotificationHook": [
          {
            "matcher": "",
            "command": "python /path/to/agent-monitor/hook.py"
          }
        ],
        "PreToolUseHook": [...],
        "PostToolUseHook": [...],
        "StopHook": [...]
      }
    }

The hook auto-detects:
  - repo: from git remote origin or directory name
  - worktree: from current directory name (typically includes branch for worktrees)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# Import from report.py (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from report import report_status, clear_status, get_status_dir


def get_git_info() -> Tuple[Optional[str], Optional[str]]:
    """
    Get repo name and worktree name from git.
    
    Returns:
        (repo_name, worktree_name) tuple
    """
    repo_name = None
    worktree_name = None
    
    try:
        # Get repo name from remote origin URL
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract repo name from various URL formats:
            # https://github.com/user/repo.git -> repo
            # git@github.com:user/repo.git -> repo
            # /path/to/repo -> repo
            match = re.search(r'[/:]([^/:]+?)(?:\.git)?$', url)
            if match:
                repo_name = match.group(1)
        
        # Fallback: use git root directory name as repo
        if not repo_name:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                repo_name = Path(result.stdout.strip()).name
        
        # Get worktree name from current directory
        # For worktrees, this is typically something like "repo-feature-branch"
        worktree_name = Path.cwd().name
        
    except Exception:
        pass
    
    return repo_name, worktree_name


def get_identity() -> Tuple[str, str]:
    """
    Get repo and worktree identity for this agent.
    
    Priority:
    1. CLI arguments (repo, worktree)
    2. Environment variables (AGENT_REPO, AGENT_WORKTREE)
    3. Git detection
    4. Current directory name
    
    Returns:
        (repo, worktree) tuple
    """
    # 1. CLI arguments
    repo_arg = sys.argv[1] if len(sys.argv) > 1 else None
    worktree_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 2. Environment variables
    repo_env = os.environ.get("AGENT_REPO")
    worktree_env = os.environ.get("AGENT_WORKTREE")
    
    # 3. Git detection
    git_repo, git_worktree = get_git_info()
    
    # 4. Fallback to current directory
    cwd_name = Path.cwd().name
    
    # Resolve with priority
    repo = repo_arg or repo_env or git_repo or "_default"
    worktree = worktree_arg or worktree_env or git_worktree or cwd_name
    
    return repo, worktree


def extract_summary_from_content(content: str) -> Optional[str]:
    """
    Extract a summary from message content.
    
    Looks for:
    1. Explicit [STATUS: ...] tags
    2. First sentence/line as fallback
    """
    if not content:
        return None
    
    # Look for explicit status tag: [STATUS: This is my current status]
    status_match = re.search(r'\[STATUS:\s*([^\]]+)\]', content, re.IGNORECASE)
    if status_match:
        return status_match.group(1).strip()
    
    # Look for a question (indicates waiting for input)
    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip()
        if line.endswith('?') and len(line) > 10:
            return line[:100]  # First question found
    
    # Fallback: first non-empty line, truncated
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('```'):
            return line[:100]
    
    return None


def detect_waiting_for_input(content: str) -> bool:
    """Detect if the message is asking for user input."""
    if not content:
        return False
    
    content_lower = content.lower()
    
    # Strong indicators of waiting for input
    waiting_patterns = [
        r'\?$',  # Ends with question mark
        r'should i\b',
        r'would you like',
        r'do you want',
        r'please (confirm|let me know|advise|choose|select|decide)',
        r'which (option|approach|method)',
        r'(waiting|need).*(input|decision|confirmation|response)',
        r'\[STATUS:.*waiting',
        r'what would you prefer',
        r'let me know (if|when|how|what)',
    ]
    
    for pattern in waiting_patterns:
        if re.search(pattern, content_lower):
            return True
    
    return False


def handle_notification_hook(event: dict, repo: str, worktree: str) -> None:
    """Handle NotificationHook - agent is sending a message/notification."""
    content = event.get("content", "")
    
    # Detect if waiting for input
    if detect_waiting_for_input(content):
        status = "waiting_input"
    else:
        status = "running"
    
    summary = extract_summary_from_content(content) or "Processing..."
    
    report_status(
        worktree=worktree,
        status=status,
        summary=summary,
        repo=repo,
        path=os.getcwd(),
    )


def handle_pre_tool_use(event: dict, repo: str, worktree: str) -> None:
    """Handle PreToolUseHook - agent is about to use a tool."""
    tool_name = event.get("tool_name", "unknown tool")
    
    # Create a readable summary of what's happening
    tool_descriptions = {
        "bash": "Running command",
        "read_file": "Reading file",
        "write_file": "Writing file", 
        "edit_file": "Editing file",
        "list_files": "Listing files",
        "search": "Searching",
        "grep": "Searching with grep",
        "glob": "Finding files",
    }
    
    summary = tool_descriptions.get(tool_name, f"Using {tool_name}")
    
    # Add more context if available
    tool_input = event.get("tool_input", {})
    if isinstance(tool_input, dict):
        if "command" in tool_input:
            cmd = tool_input["command"][:50]
            summary = f"Running: {cmd}"
        elif "path" in tool_input:
            path = Path(tool_input["path"]).name
            summary = f"{summary}: {path}"
    
    report_status(
        worktree=worktree,
        status="running",
        summary=summary,
        repo=repo,
        path=os.getcwd(),
    )


def handle_post_tool_use(event: dict, repo: str, worktree: str) -> None:
    """Handle PostToolUseHook - agent finished using a tool."""
    tool_name = event.get("tool_name", "unknown")
    
    # Check for errors
    tool_result = event.get("tool_result", {})
    if isinstance(tool_result, dict) and tool_result.get("error"):
        report_status(
            worktree=worktree,
            status="error",
            summary=f"Tool {tool_name} failed: {str(tool_result.get('error'))[:80]}",
            repo=repo,
            path=os.getcwd(),
        )
        return
    
    # Normal completion - brief update
    report_status(
        worktree=worktree,
        status="running",
        summary=f"Completed {tool_name}",
        repo=repo,
        path=os.getcwd(),
    )


def handle_stop_hook(event: dict, repo: str, worktree: str) -> None:
    """Handle StopHook - agent has stopped/completed."""
    reason = event.get("reason", "completed")
    
    if reason == "error":
        status = "error"
        summary = event.get("error_message", "Agent stopped with error")[:100]
    else:
        status = "idle"
        # Try to get final summary
        summary = event.get("summary", "Task completed")[:100]
    
    report_status(
        worktree=worktree,
        status=status,
        summary=summary,
        repo=repo,
        path=os.getcwd(),
    )
    )


def main():
    """Main entry point - reads hook event from stdin and processes it."""
    repo, worktree = get_identity()
    
    # Read JSON event from stdin
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            # No input - might be a simple ping, just report running
            report_status(
                worktree=worktree,
                status="running", 
                summary="Agent active",
                repo=repo,
                path=os.getcwd(),
            )
            return
        
        event = json.loads(raw_input)
    except json.JSONDecodeError as e:
        # Log error but don't fail - we don't want to break Claude Code
        print(f"Warning: Failed to parse hook event: {e}", file=sys.stderr)
        return
    
    # Determine hook type from event structure
    hook_type = event.get("hook_type", "")
    
    # Route to appropriate handler
    if hook_type == "NotificationHook" or "content" in event:
        handle_notification_hook(event, repo, worktree)
    elif hook_type == "PreToolUseHook" or ("tool_name" in event and "tool_input" in event):
        handle_pre_tool_use(event, repo, worktree)
    elif hook_type == "PostToolUseHook" or ("tool_name" in event and "tool_result" in event):
        handle_post_tool_use(event, repo, worktree)
    elif hook_type == "StopHook" or "reason" in event:
        handle_stop_hook(event, repo, worktree)
    else:
        # Unknown event type - just report running
        report_status(
            worktree=worktree,
            status="running",
            summary="Processing...",
            repo=repo,
            path=os.getcwd(),
        )


if __name__ == "__main__":
    main()
