#!/usr/bin/env python3
"""
Agent Monitor - A terminal dashboard for monitoring Claude Code agents across worktrees.

Usage:
    python monitor.py              # Run the dashboard
    python monitor.py --once       # Print status once and exit

Requires: Nerd Font (e.g., CascadiaCode Nerd Font) for icons

Status directory structure:
    ~/.agent-monitor/status/<repo>/<worktree>.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from threading import Thread, Event

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style
from rich.box import ROUNDED, HEAVY, DOUBLE, MINIMAL, SIMPLE

# Default status directory
DEFAULT_STATUS_DIR = Path.home() / ".agent-monitor" / "status"

# Cross-platform keyboard input
def get_key_non_blocking():
    """Get keyboard input without blocking. Returns None if no key pressed."""
    if sys.platform == 'win32':
        import msvcrt
        if msvcrt.kbhit():
            return msvcrt.getch().decode('utf-8', errors='ignore')
    else:
        import select
        import termios
        import tty

        # Check if stdin has data available
        if select.select([sys.stdin], [], [], 0)[0]:
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setraw(sys.stdin.fileno())
                key = sys.stdin.read(1)
                return key
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    return None

# Nerd Font icons (CascadiaCode Nerd Font / oh-my-posh compatible)
ICONS = {
    "running": "\uf46a",      # nf-oct-sync
    "waiting": "\uf444",      # nf-oct-question
    "idle": "\uf42e",         # nf-oct-check_circle
    "error": "\uf467",        # nf-oct-stop
    "unknown": "\uf4a5",      # nf-oct-unverified
    "repo": "\uf7a1",         # nf-md-git (git icon)
    "branch": "\ue725",       # nf-dev-git_branch
    "folder": "\uf74a",       # nf-md-folder_outline
    "terminal": "\uf489",     # nf-oct-terminal
}

# Modern color palette (muted, professional)
COLORS = {
    "accent": "#61afef",      # soft blue
    "success": "#98c379",     # soft green  
    "warning": "#e5c07b",     # soft yellow/amber
    "error": "#e06c75",       # soft red
    "muted": "#5c6370",       # gray
    "text": "#abb2bf",        # light gray
    "bright": "#ffffff",      # white
    "repo": "#c678dd",        # purple for repo names
}

# Status configuration with nerdfont icons
STATUS_CONFIG = {
    "running": {
        "icon": ICONS["running"],
        "color": COLORS["accent"],
        "label": "RUNNING",
    },
    "waiting_input": {
        "icon": ICONS["waiting"],
        "color": COLORS["warning"],
        "label": "WAITING",
    },
    "idle": {
        "icon": ICONS["idle"],
        "color": COLORS["success"],
        "label": "IDLE",
    },
    "error": {
        "icon": ICONS["error"],
        "color": COLORS["error"],
        "label": "ERROR",
    },
    "unknown": {
        "icon": ICONS["unknown"],
        "color": COLORS["muted"],
        "label": "UNKNOWN",
    },
}


def get_status_dir() -> Path:
    """Get the status directory, creating it if needed."""
    status_dir = Path(os.environ.get("AGENT_MONITOR_DIR", DEFAULT_STATUS_DIR))
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir


def read_agent_status(status_file: Path) -> Optional[dict]:
    """Read and parse an agent status file."""
    try:
        with open(status_file, "r") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def get_all_agents(status_dir: Path) -> dict[str, list[dict]]:
    """
    Read all agent status files from the status directory.
    
    Returns a dict mapping repo names to lists of agent statuses.
    Structure: ~/.agent-monitor/status/<repo>/<worktree>.json
    
    Also supports flat structure for backwards compatibility:
    ~/.agent-monitor/status/<worktree>.json (repo = "_default")
    """
    repos: dict[str, list[dict]] = {}
    
    if not status_dir.exists():
        return repos
    
    # Check for repo subdirectories
    for item in status_dir.iterdir():
        if item.is_dir():
            # This is a repo directory
            repo_name = item.name
            agents = []
            for status_file in item.glob("*.json"):
                data = read_agent_status(status_file)
                if data:
                    if "updated_at" not in data:
                        mtime = status_file.stat().st_mtime
                        data["updated_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    data["repo"] = repo_name  # Ensure repo is set
                    agents.append(data)
            if agents:
                # Sort agents within repo by status priority
                status_priority = {"waiting_input": 0, "running": 1, "error": 2, "idle": 3, "unknown": 4}
                agents.sort(key=lambda a: status_priority.get(a.get("status", "unknown"), 5))
                repos[repo_name] = agents
        elif item.is_file() and item.suffix == ".json":
            # Flat structure (backwards compatibility)
            data = read_agent_status(item)
            if data:
                if "updated_at" not in data:
                    mtime = item.stat().st_mtime
                    data["updated_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                repo_name = data.get("repo", "_default")
                if repo_name not in repos:
                    repos[repo_name] = []
                repos[repo_name].append(data)
    
    # Sort agents within each repo
    status_priority = {"waiting_input": 0, "running": 1, "error": 2, "idle": 3, "unknown": 4}
    for repo_name in repos:
        repos[repo_name].sort(key=lambda a: status_priority.get(a.get("status", "unknown"), 5))
    
    return repos


def format_time_ago(iso_time: str) -> str:
    """Format an ISO timestamp as a human-readable 'time ago' string."""
    try:
        # Parse the ISO timestamp
        if iso_time.endswith("Z"):
            iso_time = iso_time[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_time)
        
        # Make sure we're comparing timezone-aware datetimes
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        diff = now - dt
        seconds = int(diff.total_seconds())
        
        if seconds < 0:
            return "just now"
        elif seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"
    except (ValueError, TypeError):
        return "unknown"


def truncate_summary(summary: str, max_length: int = 70) -> str:
    """Truncate a summary string to fit in the display."""
    if len(summary) <= max_length:
        return summary
    return summary[:max_length - 3] + "..."


def build_dashboard(repos: dict[str, list[dict]], status_dir: Path) -> Panel:
    """Build the dashboard panel with repo -> worktree hierarchy."""
    
    # Calculate totals across all repos
    total_counts = {"waiting_input": 0, "running": 0, "error": 0, "idle": 0}
    total_agents = 0
    for agents in repos.values():
        for agent in agents:
            s = agent.get("status", "unknown")
            if s in total_counts:
                total_counts[s] += 1
            total_agents += 1
    
    # Build content
    content_parts = []
    
    if not repos:
        # Empty state
        table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
        table.add_column("", width=3)
        table.add_column("", ratio=1)
        table.add_row(
            Text(ICONS["folder"], style=COLORS["muted"]),
            Text(f"No agents found. Watching {status_dir}", style=COLORS["muted"]),
        )
        content_parts.append(table)
    else:
        # Sort repos: those with waiting_input first, then by name
        def repo_priority(repo_name: str) -> tuple:
            agents = repos[repo_name]
            has_waiting = any(a.get("status") == "waiting_input" for a in agents)
            has_running = any(a.get("status") == "running" for a in agents)
            has_error = any(a.get("status") == "error" for a in agents)
            return (not has_waiting, not has_error, not has_running, repo_name)
        
        sorted_repos = sorted(repos.keys(), key=repo_priority)
        
        for repo_idx, repo_name in enumerate(sorted_repos):
            agents = repos[repo_name]
            
            # Repo header
            repo_header = Table(show_header=False, box=None, padding=(0, 0), expand=True)
            repo_header.add_column("", width=3)
            repo_header.add_column("", ratio=1)
            
            # Count statuses for this repo
            repo_waiting = sum(1 for a in agents if a.get("status") == "waiting_input")
            repo_running = sum(1 for a in agents if a.get("status") == "running")
            repo_error = sum(1 for a in agents if a.get("status") == "error")
            
            repo_label = Text()
            repo_label.append(f"{ICONS['repo']} ", style=COLORS["repo"])
            display_name = repo_name if repo_name != "_default" else "default"
            repo_label.append(display_name, style=Style(color=COLORS["repo"], bold=True))
            
            # Add counts inline
            counts_text = Text("  ")
            if repo_waiting > 0:
                counts_text.append(f"{repo_waiting}w ", style=COLORS["warning"])
            if repo_running > 0:
                counts_text.append(f"{repo_running}r ", style=COLORS["accent"])
            if repo_error > 0:
                counts_text.append(f"{repo_error}e ", style=COLORS["error"])
            repo_label.append_text(counts_text)
            
            repo_header.add_row("", repo_label)
            content_parts.append(repo_header)
            
            # Agents table for this repo
            table = Table(
                show_header=False,
                box=None,
                padding=(0, 2),
                expand=True,
                row_styles=[Style(color=COLORS["text"])],
            )
            
            table.add_column("", width=2)  # indent
            table.add_column("", width=2, justify="center")  # Status icon
            table.add_column("", width=20)  # worktree name
            table.add_column("", width=10)  # status
            table.add_column("", width=8, justify="right")  # time
            table.add_column("", ratio=1)  # summary
            
            for agent in agents:
                status = agent.get("status", "unknown")
                config = STATUS_CONFIG.get(status, STATUS_CONFIG["unknown"])
                
                worktree = agent.get("worktree", "unknown")
                summary = agent.get("summary", "")
                updated_at = agent.get("updated_at", "")
                
                table.add_row(
                    "",  # indent
                    Text(config["icon"], style=config["color"]),
                    Text(worktree),
                    Text(config["label"], style=config["color"]),
                    Text(format_time_ago(updated_at), style=COLORS["muted"]),
                    Text(truncate_summary(summary) if summary else "-", style=COLORS["muted"]),
                )
            
            content_parts.append(table)
            
            # Add spacing between repos (except last)
            if repo_idx < len(sorted_repos) - 1:
                spacer = Table(show_header=False, box=None, padding=(0, 0))
                spacer.add_column("")
                spacer.add_row("")
                content_parts.append(spacer)
    
    # Build header
    now = datetime.now()
    title = Text()
    title.append(f" {ICONS['terminal']} ", style=COLORS["accent"])
    title.append("agent-monitor", style=Style(color=COLORS["bright"], bold=True))
    title.append(f"  {now.strftime('%H:%M:%S')}", style=COLORS["muted"])
    
    # Subtitle with totals
    subtitle_parts = []
    if total_counts["waiting_input"] > 0:
        subtitle_parts.append(f"{total_counts['waiting_input']} waiting")
    if total_counts["running"] > 0:
        subtitle_parts.append(f"{total_counts['running']} running")
    if total_counts["error"] > 0:
        subtitle_parts.append(f"{total_counts['error']} error")
    if total_agents > 0:
        subtitle_parts.append(f"{total_agents} total")
    
    subtitle_text = " | ".join(subtitle_parts) if subtitle_parts else ""
    if subtitle_text:
        subtitle_text += " | "
    subtitle_text += "Press 'q' to quit"
    subtitle = Text(subtitle_text, style=COLORS["muted"])

    return Panel(
        Group(*content_parts),
        title=title,
        title_align="left",
        subtitle=subtitle,
        subtitle_align="right",
        border_style=Style(color=COLORS["muted"]),
        padding=(1, 1),
        box=ROUNDED,
    )


def run_dashboard(status_dir: Path, refresh_rate: float = 1.0):
    """Run the live dashboard."""
    console = Console()

    try:
        with Live(
            build_dashboard(get_all_agents(status_dir), status_dir),
            console=console,
            refresh_per_second=1,
            screen=True,
        ) as live:
            while True:
                # Check for 'q' key press
                key = get_key_non_blocking()
                if key and key.lower() == 'q':
                    break

                repos = get_all_agents(status_dir)
                live.update(build_dashboard(repos, status_dir))
                time.sleep(refresh_rate)
    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n[dim]Monitor stopped.[/dim]")


def print_once(status_dir: Path):
    """Print the dashboard once and exit."""
    console = Console()
    repos = get_all_agents(status_dir)
    console.print(build_dashboard(repos, status_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Claude Code agents across worktrees"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print status once and exit (don't run live dashboard)",
    )
    parser.add_argument(
        "--status-dir",
        type=Path,
        default=None,
        help=f"Directory containing status files (default: {DEFAULT_STATUS_DIR})",
    )
    parser.add_argument(
        "--refresh",
        type=float,
        default=1.0,
        help="Refresh rate in seconds (default: 1.0)",
    )
    
    args = parser.parse_args()
    
    status_dir = args.status_dir or get_status_dir()
    
    if args.once:
        print_once(status_dir)
    else:
        run_dashboard(status_dir, args.refresh)


if __name__ == "__main__":
    main()
