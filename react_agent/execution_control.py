"""An explicit bound on main ReAct loops, independent of graph node recursion."""


class IterationLimitReached(Exception):
    """The configured number of main agent loops has completed."""


def check_iteration_limit(state: dict, config: dict) -> None:
    limit = config.get("configurable", {}).get("max_iterations")
    if limit is None:
        return
    if type(limit) is not int or limit < 1:
        raise ValueError("max_iterations must be a positive integer")
    if int(state.get("cycle", {}).get("number", 0)) >= limit:
        raise IterationLimitReached(f"Stopped after {limit} main ReAct loops")
