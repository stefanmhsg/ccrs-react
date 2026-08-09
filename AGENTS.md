# AGENTS.md

## Scope

- Applies to the `ccrs-react` repository.

## Working Agreements

- Ask for user approval before starting a new task or expanding scope beyond the current request, to avoid focus drift.
- For complex work, look for the relevant `PLAN_*.md` file before implementing and keep it current while work proceeds. For CCRS adapter work, start with [PLAN_CCRS_README.md](PLAN_CCRS_README.md).
- If you add a Decision Log entry to an execution plan, highlight that decision explicitly to the user.

## CCRS Context

- For CCRS concepts, start with [CCRS_LIBRARY.md](../ccrs/CCRS_LIBRARY.md) in the standalone Java library repository.
- For approach-specific Java behavior, also read the opportunistic CCRS [README.md](../ccrs/ccrs-core/src/main/java/ccrs/core/opportunistic/README.md) and contingency CCRS [README.md](../ccrs/ccrs-core/src/main/java/ccrs/core/contingency/README.md).
- Treat `ccrs-langgraph` as an external package owned by the
  [ccrs repository](https://github.com/stefanmhsg/ccrs/tree/master/ccrs-langgraph).
  The application under [react_agent](react_agent) consumes it and must not
  reintroduce adapter modules under this repository.

## Verification

- Use `S:\anaconda\agent\python.exe` for Python validation in this repository unless the user provides a different interpreter.
- When adding or changing modules imported by notebook sessions, update the reload/import cell in [test_agent.ipynb](test_agent.ipynb). Reload helper modules before modules that import from them by name, so notebook runs do not keep stale objects after code changes.
