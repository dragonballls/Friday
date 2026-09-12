# Runtime contract

Friday's minimal runtime is successful only when the coding-agent loop is real and observable.

A task must have a durable ID and explicit lifecycle state. Agent activity should emit structured events for planning, tool execution, file reads/writes, tests, errors, retries, and completion. The frontend consumes those events and displays them as the live activity feed.

Voice is an input/output transport, not a separate assistant mode: spoken requests become the same coding tasks as typed requests.

The UI must never infer that coding is happening from a spinner alone. Activity comes from actual agent/runtime events.