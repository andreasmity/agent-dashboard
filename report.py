#!/usr/bin/env python3
"""
Agent Reporter - Report agent status to the monitor.

This script is used by Claude Code agents to report their status.
It can be called directly or imported as a module.

Status directory structure:
    ~/.agent-monitor/status/<repo>/<worktree>.json

Usage:
    # Report status via CLI (with repo)
    python report.py myrepo feature-auth running "Refactoring auth module"
    python report.py myrepo feature-auth waiting_input "Should I use OAuth or JWT?"
    
    # Report status via CLI (without repo - uses _default)
    python report.py feature-auth running "Working on feature"
    
    # Clear/remove an agent's status
    python report.py myrepo feature-auth --clear
    
    # Report with custom path
    python report.py myrepo feature-auth running "Working" --path /path/to/worktree
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Default status directory (same as monitor.py)
DEFAULT_STATUS_DIR = Path.home() / ".agent-monitor" / "status"

# Valid statuses
VALID_STATUSES = {"running", "waiting_input", "idle", "error"}


def get_status_dir() -> Path:
    """Get the status directory, creating it if needed."""
    status_dir = Path(os.environ.get("AGENT_MONITOR_DIR", DEFAULT_STATUS_DIR))
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir


def report_status(
    worktree: str,
    status: str,
    summary: str = "",
    repo: str = "_default",
    path: Optional[str] = None,
    status_dir: Optional[Path] = None,
) -> Path:
    """
    Report an agent's status.
    
    Args:
        worktree: Name of the worktree/agent
        status: One of: running, waiting_input, idle, error
        summary: Brief description of current state
        repo: Repository name (default: _default)
        path: Optional path to the worktree
        status_dir: Optional custom status directory
    
    Returns:
        Path to the status file that was written
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")
    
    if status_dir is None:
        status_dir = get_status_dir()
    
    # Create repo subdirectory
    repo_dir = status_dir / repo
    repo_dir.mkdir(parents=True, exist_ok=True)
    
    status_file = repo_dir / f"{worktree}.json"
    
    data = {
        "repo": repo,
        "worktree": worktree,
        "status": status,
        "summary": summary,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    if path:
        data["path"] = path
    
    with open(status_file, "w") as f:
        json.dump(data, f, indent=2)
    
    return status_file


def clear_status(
    worktree: str,
    repo: str = "_default",
    status_dir: Optional[Path] = None
) -> bool:
    """
    Clear/remove an agent's status file.
    
    Args:
        worktree: Name of the worktree/agent
        repo: Repository name (default: _default)
        status_dir: Optional custom status directory
    
    Returns:
        True if file was removed, False if it didn't exist
    """
    if status_dir is None:
        status_dir = get_status_dir()
    
    status_file = status_dir / repo / f"{worktree}.json"
    
    if status_file.exists():
        status_file.unlink()
        # Clean up empty repo directory
        repo_dir = status_file.parent
        if repo_dir.exists() and not any(repo_dir.iterdir()):
            repo_dir.rmdir()
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Report agent status to the monitor",
        usage="""
  %(prog)s <repo> <worktree> <status> [summary]    Report with repo
  %(prog)s <worktree> <status> [summary]           Report without repo (uses _default)
  %(prog)s <repo> <worktree> --clear               Clear status
  %(prog)s <worktree> --clear                      Clear status (uses _default)
        """
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="[repo] worktree [status] [summary]",
    )
    parser.add_argument(
        "--path",
        help="Path to the worktree",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear/remove the agent's status",
    )
    parser.add_argument(
        "--status-dir",
        type=Path,
        default=None,
        help=f"Directory for status files (default: {DEFAULT_STATUS_DIR})",
    )
    
    args = parser.parse_args()
    positional = args.args
    
    if args.clear:
        # Clear mode: expect [repo] worktree
        if len(positional) == 1:
            repo = "_default"
            worktree = positional[0]
        elif len(positional) == 2:
            repo = positional[0]
            worktree = positional[1]
        else:
            parser.error("Usage: report.py [repo] worktree --clear")
        
        removed = clear_status(worktree, repo, args.status_dir)
        if removed:
            print(f"Cleared status for '{repo}/{worktree}'")
        else:
            print(f"No status file found for '{repo}/{worktree}'")
        return
    
    # Report mode: figure out if repo was provided
    # Heuristic: if second arg is a valid status, then first arg is worktree (no repo)
    # Otherwise, first arg is repo, second is worktree
    
    if len(positional) < 2:
        parser.error("Usage: report.py [repo] worktree status [summary]")
    
    if positional[1] in VALID_STATUSES:
        # No repo provided: worktree status [summary]
        repo = "_default"
        worktree = positional[0]
        status = positional[1]
        summary = positional[2] if len(positional) > 2 else ""
    elif len(positional) >= 3 and positional[2] in VALID_STATUSES:
        # Repo provided: repo worktree status [summary]
        repo = positional[0]
        worktree = positional[1]
        status = positional[2]
        summary = positional[3] if len(positional) > 3 else ""
    else:
        parser.error(f"Invalid status. Must be one of: {VALID_STATUSES}")
    
    status_file = report_status(
        worktree=worktree,
        status=status,
        summary=summary,
        repo=repo,
        path=args.path,
        status_dir=args.status_dir,
    )
    print(f"Status reported: {status_file}")


if __name__ == "__main__":
    main()
