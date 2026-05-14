__all__ = [
    "CcrsAgentState",
    "CcrsRuntime",
    "CcrsRuntimeError",
    "get_default_runtime",
    "make_opportunistic_ccrs_node",
    "opportunistic_ccrs_node",
]


def __getattr__(name):
    if name in {"CcrsRuntime", "CcrsRuntimeError", "get_default_runtime"}:
        from react_agent.ccrs.runtime import (
            CcrsRuntime,
            CcrsRuntimeError,
            get_default_runtime,
        )

        exports = {
            "CcrsRuntime": CcrsRuntime,
            "CcrsRuntimeError": CcrsRuntimeError,
            "get_default_runtime": get_default_runtime,
        }
        globals().update(exports)
        return exports[name]

    if name == "CcrsAgentState":
        from react_agent.ccrs.state import CcrsAgentState

        globals()[name] = CcrsAgentState
        return CcrsAgentState

    if name in {"make_opportunistic_ccrs_node", "opportunistic_ccrs_node"}:
        from react_agent.ccrs.opportunistic import make_opportunistic_ccrs_node

        exports = {
            "make_opportunistic_ccrs_node": make_opportunistic_ccrs_node,
            "opportunistic_ccrs_node": make_opportunistic_ccrs_node(),
        }
        globals().update(exports)
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
