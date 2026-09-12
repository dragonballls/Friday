# Barebones runtime status

The minimal UI should always expose:

- **Idle / Thinking / Coding / Testing / Waiting / Error / Completed** state.
- The current task description.
- The current agent step and most recent action.
- Files touched or inspected.
- Commands/tests started and their result.
- A durable task identifier so interrupted work can be resumed.
- A visible last-updated timestamp.

The activity feed should be append-only for a task and persisted locally. On restart, the UI should restore the most recent task and its last known state. The agent must never pretend a task is complete without an explicit successful completion signal.