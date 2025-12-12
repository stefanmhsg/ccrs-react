import os
import asyncio
import importlib
from datetime import datetime
from typing import Optional, Any

from react_agent.settings import settings
from react_agent.logging_config import setup_logging
from react_agent.runner import run_query_async, run_query_sync

def get_graph_builder(graph_name: str):
    try:
        module = importlib.import_module(f"react_agent.{graph_name}")
        return getattr(module, "build_graph")
    except ImportError:
        raise ValueError(f"Graph module 'react_agent.{graph_name}' not found.")
    except AttributeError:
        raise ValueError(f"Module 'react_agent.{graph_name}' does not have a 'build_graph' function.")

async def launch_agent(
    query: str,
    agent_name: Optional[str] = None,
    graph_name: str = "graph",
    recursion_limit: Optional[int] = None,
    log_level: Optional[str] = None,
    run_mode: Optional[str] = None,
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
        **kwargs: Additional configuration to pass to the agent.
    """
    # Determine configuration values, preferring arguments over settings defaults
    current_agent_name = agent_name or settings.agent_name
    current_recursion_limit = recursion_limit or settings.recursion_limit
    current_log_level = log_level or settings.log_level
    current_run_mode = run_mode or settings.run_mode
    
    # Set environment variable
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    run_name = f"{current_agent_name}_{datetime.now():%Y%m%d_%H%M%S}"

    # Configure logging
    logger = setup_logging(level=current_log_level, run_name=run_name)
    logger.info(f"Starting agent {current_agent_name} with graph {graph_name}")

    # Build the graph
    try:
        build_graph = get_graph_builder(graph_name)
        graph = build_graph()
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        raise

    # Save the graph visualization
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
            **kwargs
        }
    }

    if current_run_mode == "async":
        logger.info("Running in async mode")
        await run_query_async(graph, query, run_name, run_config)
    else:
        logger.info("Running in sync mode")
        run_query_sync(graph, query, run_name, run_config)
    
    logger.info("Agent finished")
