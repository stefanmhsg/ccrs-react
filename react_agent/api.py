import os
import asyncio
import importlib
import inspect
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

from react_agent.utils.settings import settings
from react_agent.utils.logging_config import setup_logging
from react_agent.runner import run_query_async, run_query_sync
from react_agent.execution_control import experiment_limits

def get_graph_builder(graph_name: str):
    try:
        module = importlib.import_module(f"react_agent.graph.{graph_name}")
        return getattr(module, "build_graph")
    except ImportError:
        raise ValueError(f"Graph module 'react_agent.graph.{graph_name}' not found.")
    except AttributeError:
        raise ValueError(f"Module 'react_agent.graph.{graph_name}' does not have a 'build_graph' function.")


def _graph_build_kwargs(build_graph, kwargs: dict[str, Any]) -> dict[str, Any]:
    signature = inspect.signature(build_graph)
    accepted = {}
    for name, parameter in signature.parameters.items():
        if parameter.kind not in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            continue
        if name in kwargs:
            accepted[name] = kwargs[name]
    return accepted

async def launch_agent(
    query: str,
    agent_name: Optional[str] = None,
    graph_name: str = "graph",
    recursion_limit: Optional[int] = None,
    log_level: Optional[str] = None,
    run_mode: Optional[str] = None,
    run_name: Optional[str] = None,
    save_graph: bool = True,
    experiment_stop_configuration: Optional[dict] = None,
    **kwargs: Any
):
    """
    Launch the agent with the specified configuration.
    
    Args:
        query: The query to run.
        agent_name: Name of the agent (overrides settings).
        graph_name: Name of the graph module to use (default: "graph").
        recursion_limit: Recursion limit (overrides settings).
        log_level: Logging level (overrides settings).
        run_mode: "sync" or "async" (overrides settings).
        run_name: Optional unique log/trace identity; does not change the maze agent name.
        save_graph: Save a graph rendering for interactive use; disabled by automated collection.
        max_iterations: Optional positive main-loop bound, passed in kwargs. Independent of recursion_limit.
        experiment_stop_configuration: Experiment budgets and ordered zone boundaries; defaults to 50 calls/1000 cycles.
        **kwargs: Additional configuration to pass to the agent.
    """
    # Determine configuration values, preferring arguments over settings defaults
    current_agent_name = agent_name or settings.agent_name
    current_recursion_limit = recursion_limit or settings.recursion_limit
    current_log_level = log_level or settings.log_level
    current_run_mode = run_mode or settings.run_mode
    
    # Set environment variable
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    run_name = run_name or f"{current_agent_name}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_name) or not re.fullmatch(re.escape(current_agent_name) + r"_[A-Za-z0-9_-]+", run_name):
        raise ValueError("run_name must be a safe filename prefixed by the maze agent name")
    if (Path("logs") / f"{run_name}.log").exists():
        raise ValueError("Refusing to overwrite an existing invocation log")
    limit = kwargs.get("max_iterations")
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("max_iterations must be a positive integer")
    stop_limits = experiment_limits(experiment_stop_configuration)

    # Configure logging
    logger = setup_logging(level=current_log_level, run_name=run_name)
    logger.info(f"Starting agent {current_agent_name} with graph {graph_name}")
    logger.info("[REACT-EXPERIMENT-LIMITS] %s", json.dumps(stop_limits, sort_keys=True))

    # Build the graph
    try:
        build_graph = get_graph_builder(graph_name)
        graph = build_graph(**_graph_build_kwargs(build_graph, kwargs))
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        raise

    # Save the graph visualization
    if save_graph:
        try:
            # Use graph_name for unique files per graph type
            graph_filename = f"{graph_name}.png"
            with open(graph_filename, "wb") as f:
                f.write(graph.get_graph().draw_mermaid_png())
            logger.info(f"Graph visualization saved to {graph_filename}")
        except Exception as e:
            logger.warning(f"Could not save graph visualization: {e}")

    # Prepare configuration for the run
    run_config = {
        "recursion_limit": current_recursion_limit,
        "configurable": {
            "agent_name": current_agent_name,
            "llm_model": settings.llm_model,
            "llm_temperature": settings.llm_temperature,
            "llm_reasoning_effort": settings.llm_reasoning_effort,
            "llm_seed": settings.llm_seed,
            "llm_message_window_max_messages": settings.llm_message_window_max_messages,
            "llm_message_window_max_tokens": settings.llm_message_window_max_tokens,
            **kwargs,
            "experiment_stop_configuration": stop_limits,
        }
    }

    if current_run_mode == "async":
        logger.info("Running in async mode")
        await run_query_async(graph, query, run_name, run_config)
    else:
        logger.info("Running in sync mode")
        run_query_sync(graph, query, run_name, run_config)
    
    logger.info("Agent finished")
