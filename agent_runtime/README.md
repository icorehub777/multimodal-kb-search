# Agent Runtime

`agent_runtime/` is the formal runtime workspace root for Agent operations.

- `memory.md` stores cross-session handoff notes.
- `query_results/` stores user-facing query outputs.
- `workspace/` stores per-task working files.
- `_internal/` stores runtime details that users should not edit directly.

Runtime-generated files should stay inside this directory.
