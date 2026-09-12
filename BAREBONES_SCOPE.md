# Barebones Friday scope

The existing Friday implementation remains preserved in Git history and on its existing branches.

This branch is intentionally reduced to the core workflow:

1. User can speak or type a coding request.
2. Friday runs its coding agent and works autonomously within the configured project workspace.
3. Friday exposes a live activity view showing current task, agent state, files being changed, commands/tests, and completion/error state.
4. Work state and agent progress are persisted so an interruption can be recovered rather than silently losing the task.
5. The app should launch without PowerShell/terminal windows for normal use.

Nonessential/default UI such as personas, holodeck/holographic presentation, decorative panels, and unrelated feature surfaces should not be part of the barebones default experience. Existing implementations are not deleted; this is a focused new branch.