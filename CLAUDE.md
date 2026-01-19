# Agent Monitor Integration

This project uses agent-monitor to track status across worktrees. When working in this codebase, follow these conventions to ensure your status is properly reported.

## Status Reporting

The monitoring system will automatically detect your status through Claude Code hooks. However, you can help by including explicit status markers in your messages when appropriate.

### Explicit Status Tags

When you need input or want to clearly communicate your status, include a `[STATUS: ...]` tag in your message:

```
[STATUS: Waiting for decision on authentication approach]

I've analyzed the codebase and found two viable options:
1. OAuth 2.0 - better for external integrations
2. JWT with refresh tokens - simpler implementation

Which approach would you prefer?
```

### When to Use Status Tags

Use `[STATUS: ...]` tags when:
- You need a decision from the user
- You've completed a significant milestone
- You've encountered a blocking issue
- You want to clearly summarize your current activity

Examples:
```
[STATUS: Implementing user authentication module]
[STATUS: Waiting for API key to proceed]
[STATUS: Completed database migration - ready for review]
[STATUS: Blocked by failing test in auth.spec.ts]
```

### Auto-Detection

The monitor also auto-detects:
- **Questions ending in `?`** → likely waiting for input
- **Phrases like "should I", "would you like"** → waiting for input
- **Tool usage** → running
- **Errors** → error status

## Best Practices

1. **Be concise**: Status summaries are truncated to ~100 characters
2. **Be specific**: "Refactoring auth module" is better than "Working"
3. **Ask clear questions**: When you need input, ask a direct question
4. **One status per message**: The monitor uses the first `[STATUS: ...]` found

## Checking Your Status

The human can see your status in the agent-monitor dashboard:
- Your worktree name
- Current status (running/waiting/idle/error)
- Your summary message
- Time since last update
