"""Launch one frozen notebook-derived specification in a fresh Python process.

The experiment repository owns selection, dependency preparation and supervision.
This application entry point owns resolving its prompts, environment and launch API.
It intentionally imports agent dependencies only after loading the environment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch-spec", required=True, type=Path)
    parser.add_argument("--start-gate", type=Path, help="Supervisor receipt permitting imports after process ownership is established.")
    args = parser.parse_args(argv)
    if args.start_gate:
        deadline = time.monotonic() + 30
        while not args.start_gate.is_file():
            if time.monotonic() >= deadline:
                raise TimeoutError("Supervisor did not establish process ownership")
            time.sleep(.05)
    spec = json.loads(args.launch_spec.read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1:
        raise ValueError("Expected launch specification schema_version=1")
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    from react_agent.api import launch_agent
    from react_agent.prompts import user_query
    from react_agent.utils.settings import settings
    from react_agent.execution_control import experiment_limits
    parameters = dict(spec["parameters"])
    parameters["experiment_stop_configuration"] = experiment_limits(parameters.get("experiment_stop_configuration"))
    query = spec["query"]
    if query.get("reference") not in (None, "USER_QUERY", "USER_QUERY_CCRS"):
        raise ValueError("Unknown application query reference")
    parameters["query"] = getattr(user_query, query["reference"]) if query.get("reference") else query["literal"]
    # Retain effective, non-secret model/runtime settings alongside the frozen
    # launch inputs. Never serialize the environment or API credentials.
    effective = {name: getattr(settings, name) for name in (
        "llm_model_profile", "llm_model", "llm_temperature", "llm_reasoning_effort", "llm_seed",
        "llm_message_window_max_messages", "llm_message_window_max_tokens", "recursion_limit", "run_mode", "log_level")}
    effective.update(parameters)
    (args.launch_spec.parent / "effective-settings.json").write_text(
        json.dumps(effective, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        asyncio.run(launch_agent(**parameters))
    finally:
        # Allow the supervisor to distinguish a returned graph from process exit;
        # tracing or the embedded JVM may still take time to shut down.
        try:
            from langsmith.run_trees import get_cached_client
            get_cached_client().flush()
        finally:
            logging.shutdown()


if __name__ == "__main__":
    main()
