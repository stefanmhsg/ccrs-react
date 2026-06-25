"""Default user queries for local ReAct agent runs."""

BASE_MAZE_TASK = """
You are an agent navigating an HTTP/RDF maze.

Goal: reach the maze exit.

Use the system prompt as the authoritative action contract. It contains the
current embodied cell, bootstrap instructions when needed, legal perception and
navigation rules, and exact tool-call shapes.

After bootstrap, operate in this loop:
1. Perceive the tracked current cell.
2. Use the parsed advertised navigation options and any current-cell interaction
   affordances to choose the next action.
3. Use `http_post` either to navigate to an advertised target or to perform a
   valid interaction on the current cell.
4. Continue until the exit is reached. The agentic loop will terminate when you
   are embodied in the exit cell.
""".strip()


CCRS_TASK_ADDENDUM = """

The `escalate_to_contingency_ccrs` tool is available to you for escalation when you are about to
fail, do not know how to proceed, are confused, see unexpected environment
structure, or are making no progress, use it before spending more normal tool
calls.
""".strip()


USER_QUERY = BASE_MAZE_TASK
USER_QUERY_CCRS = f"{BASE_MAZE_TASK}\n\n{CCRS_TASK_ADDENDUM}"
