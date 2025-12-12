import argparse
import os
import asyncio
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)
from datetime import datetime
from react_agent.settings import Settings, settings
from react_agent.logging_config import setup_logging
from react_agent.graph import build_graph
from react_agent.runner import run_query_async, run_query_sync

QUERY_V1 = (
    "You need to navigate a linked data maze: entrypoint is = http://127.0.1.1:8080/maze (look for xhv:start to see where to enter the maze). "
    "If you perform a get request it will return RDF triples describing the cell, what it contains and what connections it has. "
    "GET is only allowed on cells you are currently in. POST requests are used to move between cells - only allowed to adjacent cells. POST is also used to interact cells - only allowed for cells you are currently in. "
    "Reach the exit by navigating the maze. "
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
    "So typically you would GET current, POST to move to adjacent cell, GET new cell, POST to interact if needed, etc., until you reach the exit."
    )

QUERY_V2 = (
    "You must navigate a linked data maze. "
    "The maze entrypoint is http://127.0.1.1:8080/maze. "
    "Look for the xhv:start triple to determine the first cell. "

    "Each cell is described by RDF returned from GET requests. "
    "A GET request is only allowed on the cell you are currently in. "

    "Movement and interactions use POST requests. "
    "Rules for POST: "
    "1. POST to move to a different cell is only allowed if that cell is adjacent to your current cell. "
    "2. POST to interact with a cell is only allowed for the cell you are currently in. "
    "3. POST requires content type text/turtle with RDF triples in the body. "

    "Format for movement: "
    "POST <TargetCellURI> "
    "Body: "
    "<http://127.0.1.1:8080/agents/<YourName>> "
    "<https://paul.ti.rw.fau.de/~am52etar/dynmaze/dynmaze#entersFrom> "
    "<OriginCellURI> . "

    "Format for interactions: "
    "POST <RequestURI> "
    "Body: "
    "<RequestURI> <NeededPropertyIRI> \"Value\" . "

    "Your task is to reach the exit of the maze by repeatedly: "
    "1. GET the current cell to inspect its triples. "
    "2. Decide whether to interact with the cell or move to an adjacent cell. "
    "3. POST to perform the chosen action. "
    "4. Continue until the exit cell is reached. "
    )

def parse_args():
    parser = argparse.ArgumentParser(description="Run the ReAct CCRS Agent")

    parser.add_argument("--recursion-limit", type=int, help="Override recursion limit")
    parser.add_argument("--agent-name", type=str, help="Name of the agent run")
    parser.add_argument("--log-level", type=str, help="Logging level")
    parser.add_argument("--query", type=str, help="User query")

    return parser.parse_args()


def main():

    # Parse command-line arguments
    args = parse_args()

    # Update global settings with CLI overrides
    if args.recursion_limit:
        settings.recursion_limit = args.recursion_limit
    if args.agent_name:
        settings.agent_name = args.agent_name
    if args.log_level:
        settings.log_level = args.log_level

    # Set environment variable
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


    run_name = f"{settings.agent_name}_{datetime.now():%Y%m%d_%H%M%S}"

    # Configure logging
    logger = setup_logging(level=settings.log_level, run_name=run_name)
    logger.info("Starting agent")


    # Build the graph
    graph = build_graph()

    # Define the query
    query = args.query or QUERY_V2

    # Prepare configuration for the run
    run_config = {
        "recursion_limit": settings.recursion_limit,
        "configurable": {
            "agent_name": settings.agent_name,
            "llm_model": settings.llm_model,
            "llm_temperature": settings.llm_temperature,
        }
    }

    if settings.run_mode == "async":
        # Run the query asynchronously
        logger.info("Running in async mode")
        asyncio.run(run_query_async(graph, query, run_name, run_config))
    else:
        # Alternatively, run the query synchronously
        logger.info("Running in sync mode")
        run_query_sync(graph, query, run_name, run_config)
    
    logger.info("Agent finished")


if __name__ == "__main__":
    main()
