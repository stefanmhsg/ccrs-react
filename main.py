import argparse
import os
import asyncio
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)
from datetime import datetime
from react_agent.settings import Settings
from react_agent.logging_config import setup_logging
from react_agent.graph import build_graph
from react_agent.runner import run_query_async, run_query_sync


def parse_args():
    parser = argparse.ArgumentParser(description="Run the ReAct CCRS Agent")

    parser.add_argument("--recursion_limit", type=int, help="Override recursion limit")
    parser.add_argument("--agent_name", type=str, help="Name of the agent run")
    parser.add_argument("--log_level", type=str, help="Logging level")
    parser.add_argument("--query", type=str, help="User query")

    return parser.parse_args()


def main():

    # Parse command-line arguments
    args = parse_args()

    # Load .env and environment settings first
    base_settings = Settings()

    # Merge CLI overrides
    config = Settings(
        recursion_limit = args.recursion_limit or base_settings.recursion_limit,
        agent_name      = args.agent_name or base_settings.agent_name,
        log_level       = args.log_level or base_settings.log_level,


        # values required by BaseSettings must still be filled
        llm_model       = base_settings.llm_model,
        llm_temperature = base_settings.llm_temperature,
        langchain_project = base_settings.langchain_project,
    )

    # Set environment variable
    os.environ["LANGCHAIN_PROJECT"] = config.langchain_project


    run_name = f"{config.agent_name}_{datetime.now():%Y%m%d_%H%M%S}"

    # Configure logging
    logger = setup_logging(level=config.log_level, run_name=run_name)
    logger.info("Starting agent")


    # Build the graph
    graph = build_graph()

    # Define the query
    query = (
        "you need to navigate a linked data maze: entrypoint is = http://127.0.1.1:8080/maze (look for xhv:start to see where to enter the maze) and if you perform a get request it will return RDF triples describing the cell (only allowed for current cell), what it contains and what connections it has. reach the exit by navigating (allowed only to adjacent cells) the maze. "
        "POST for moving from a cell to another expects text/turtle, with RDF format body. "
        "Example format for moving: "
        "POST <TargetCellURI> "
        "Body: "
        "<http://127.0.1.1:8080/agents/<YourName>> <https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> <OriginCellURI> . "
        "POST for interacting with a cell expects text/turtle, with RDF format body. "
        "Example format for interaction: "
        "POST <RequestURI> "
        "Body: "
        "<Same as <RequestURI>> <NeededPropertyIRI> \"Value\" . "
    )

    if config.run_mode == "async":
        # Run the query asynchronously
        logger.info("Running in async mode")
        asyncio.run(run_query_async(graph, query, run_name, config.recursion_limit))
    else:
        # Alternatively, run the query synchronously
        logger.info("Running in sync mode")
        run_query_sync(graph, query, run_name, config.recursion_limit)
    
    logger.info("Agent finished")


if __name__ == "__main__":
    main()
