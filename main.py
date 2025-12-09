import os
import asyncio
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)

from datetime import datetime

from react_agent.logging_config import setup_logging

from react_agent.graph import build_graph
from react_agent.runner import run_query_async, run_query_sync


def main():

    # Load environment variables
    os.environ["LANGCHAIN_PROJECT"] = "react"
    run_name = f"ReAct_CCRS_{datetime.now():%Y%m%d_%H%M%S}"

    # Configure logging
    logger = setup_logging()
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

    # Run the query asynchronously
    #asyncio.run(run_query_async(graph, query, run_name))

    # Alternatively, run the query synchronously
    run_query_sync(graph, query, run_name)

    logger.info("Agent finished")


if __name__ == "__main__":
    main()
