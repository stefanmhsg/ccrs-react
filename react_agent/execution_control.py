"""Experiment termination budgets, independent of graph node recursion."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


class ExperimentLimitReached(Exception):
    """An experiment budget ended the run, with inspectable counter evidence."""

    def __init__(self, reason: str, progress: dict, cycle: int, limits: dict):
        self.reason = reason
        index = progress["zone_index"]
        self.details = {"reason": reason, "cycle": cycle,
                        "zone": limits["zones"][index]["name"] if index < len(limits["zones"]) else None,
                        "zone_cycles": cycle - progress["zone_started_cycle"],
                        "progress": deepcopy(progress), "limits": deepcopy(limits)}
        super().__init__(reason)


def experiment_limits(overrides: dict | None = None) -> dict:
    defaults = json.loads(Path(__file__).with_name("experiment_stop_defaults.json").read_text(encoding="utf-8"))
    if overrides is not None and not isinstance(overrides, dict):
        raise ValueError("experiment_stop_configuration must be a dictionary")
    limits = {**defaults, **(overrides or {})}
    if set(limits) != set(defaults):
        raise ValueError("Unknown experiment stop configuration key")
    for key in ("tool_invocations_without_move", "cycles_per_zone"):
        if type(limits[key]) is not int or limits[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    zones = limits["zones"]
    if not isinstance(zones, list) or not zones:
        raise ValueError("Experiment zones must be a nonempty ordered list")
    previous = None
    names = set()
    exits = set()
    for zone in zones:
        if not isinstance(zone, dict) or set(zone) != {"name", "entry", "exit"}:
            raise ValueError("Each zone requires name, entry and exit")
        if not isinstance(zone["name"], str) or not zone["name"] or zone["name"] in names:
            raise ValueError("Zone names must be nonempty and unique")
        if any(not isinstance(zone[k], str) or not re.fullmatch(r"cells/\d+(?:/\d+)?", zone[k]) for k in ("entry", "exit")):
            raise ValueError("Zone boundaries must be canonical cells/... identifiers")
        if zone["entry"] == zone["exit"] or zone["exit"] in exits or previous is not None and zone["entry"] != previous:
            raise ValueError("Zone boundaries must form an ordered chain without repeated exits")
        names.add(zone["name"])
        exits.add(zone["exit"])
        previous = zone["exit"]
    return deepcopy(limits)


def configured_limits(config: dict) -> dict:
    return experiment_limits(config.get("configurable", {}).get("experiment_stop_configuration"))


def cell_id(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        path = urlsplit(value).path.strip("/")
    except ValueError:
        return None
    return path if re.fullmatch(r"cells/\d+(?:/\d+)?", path) else None


def progress_for(state: dict) -> dict:
    progress = deepcopy(state.get("experiment_progress") or {
        "tool_invocations_without_move": 0, "current_cell": None,
        "zone_index": 0, "zone_started_cycle": 0, "completed_zones": [],
    })
    if progress["current_cell"] is None:
        progress["current_cell"] = cell_id(state.get("current_cell"))
    return progress


def record_tool(progress: dict, *, call: dict, successful_move: bool, cycle: int, limits: dict) -> None:
    """Count one requested invocation after its result; placement/self-posts do not reset."""
    progress["tool_invocations_without_move"] += 1
    args = call.get("args") or {}
    target = cell_id(args.get("url")) if isinstance(args, dict) else None
    if successful_move and target is not None:
        previous = progress["current_cell"]
        progress["current_cell"] = target
        if previous is not None and previous != target:
            progress["tool_invocations_without_move"] = 0
            index = progress["zone_index"]
            if index < len(limits["zones"]) and target == limits["zones"][index]["exit"]:
                progress["completed_zones"].append(limits["zones"][index]["name"])
                progress["zone_index"] += 1
                progress["zone_started_cycle"] = cycle
    if progress["tool_invocations_without_move"] >= limits["tool_invocations_without_move"]:
        raise ExperimentLimitReached("no_movement_tool_limit", progress, cycle, limits)


def check_zone_budget(progress: dict, cycle: int, limits: dict) -> None:
    if progress["zone_index"] < len(limits["zones"]) and cycle - progress["zone_started_cycle"] >= limits["cycles_per_zone"]:
        raise ExperimentLimitReached("zone_cycle_limit", progress, cycle, limits)


def experiment_budget_node(state: dict, config) -> dict:
    """Check at the end of action execution, allowing a boundary move on cycle 1000."""
    check_zone_budget(progress_for(state), int(state.get("cycle", {}).get("number", 0)), configured_limits(config))
    return {}


def account_control_calls(state: dict, config: dict) -> dict:
    """Count escalation/stop control calls handled outside the HTTP tool node."""
    progress = progress_for(state)
    cycle = int(state.get("cycle", {}).get("number", 0))
    limits = configured_limits(config)
    last = state["messages"][-1]
    for call in getattr(last, "tool_calls", None) or []:
        record_tool(progress, call=call, successful_move=False, cycle=cycle, limits=limits)
    check_zone_budget(progress, cycle, limits)
    return {"experiment_progress": progress}


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
