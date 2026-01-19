#!/usr/bin/env python3
"""
Demo script - creates sample status files to test the monitor.

Run this first to populate some test data:
    python demo.py

Then run the monitor:
    python monitor.py --once
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Same default as monitor.py
DEFAULT_STATUS_DIR = Path.home() / ".agent-monitor" / "status"

def create_demo_data():
    status_dir = Path(os.environ.get("AGENT_MONITOR_DIR", DEFAULT_STATUS_DIR))
    
    now = datetime.now(timezone.utc)
    
    # Sample repos with their agents
    repos = {
        "webapp": [
            {
                "worktree": "feature-auth",
                "status": "waiting_input",
                "summary": "Should I use OAuth 2.0 or JWT for the new auth system?",
                "path": "/home/user/webapp-feature-auth",
                "updated_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "worktree": "bugfix-api",
                "status": "running",
                "summary": "Refactoring error handling in api/routes.ts",
                "path": "/home/user/webapp-bugfix-api",
                "updated_at": (now - timedelta(seconds=30)).isoformat(),
            },
            {
                "worktree": "feature-ui",
                "status": "idle",
                "summary": "Completed: Added dark mode toggle component",
                "path": "/home/user/webapp-feature-ui",
                "updated_at": (now - timedelta(minutes=5)).isoformat(),
            },
        ],
        "backend-services": [
            {
                "worktree": "refactor-db",
                "status": "waiting_input",
                "summary": "Should I migrate existing user data or create fresh tables?",
                "path": "/home/user/backend-refactor-db",
                "updated_at": (now - timedelta(minutes=8)).isoformat(),
            },
            {
                "worktree": "hotfix-login",
                "status": "error",
                "summary": "Build failed: Cannot find module '@auth/core'",
                "path": "/home/user/backend-hotfix-login",
                "updated_at": (now - timedelta(minutes=1)).isoformat(),
            },
        ],
        "ml-pipeline": [
            {
                "worktree": "experiment-bert",
                "status": "running",
                "summary": "Training model: epoch 42/100, loss=0.0234",
                "path": "/home/user/ml-experiment-bert",
                "updated_at": (now - timedelta(seconds=10)).isoformat(),
            },
            {
                "worktree": "data-cleaning",
                "status": "idle",
                "summary": "Completed preprocessing of 50k samples",
                "path": "/home/user/ml-data-cleaning",
                "updated_at": (now - timedelta(minutes=15)).isoformat(),
            },
        ],
    }
    
    for repo_name, agents in repos.items():
        repo_dir = status_dir / repo_name
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        for agent in agents:
            agent["repo"] = repo_name
            status_file = repo_dir / f"{agent['worktree']}.json"
            with open(status_file, "w") as f:
                json.dump(agent, f, indent=2)
            print(f"Created: {status_file}")
    
    print(f"\nDemo data created in: {status_dir}")
    print(f"  Repos: {list(repos.keys())}")
    print("\nNow run: python monitor.py --once")
    print("Or for live: python monitor.py")


if __name__ == "__main__":
    create_demo_data()
