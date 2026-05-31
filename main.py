import argparse
import asyncio
import os
from dotenv import load_dotenv
from react_agent.api import launch_agent
from react_agent.ccrs.capabilities import (
    CCRS_A2A_MODULE,
    CCRS_CORE_MODULE,
    CCRS_LANGCHAIN4J_MODULE,
)
from react_agent.prompts.user_query import USER_QUERY
from react_agent.utils.settings import settings

load_dotenv(dotenv_path=".env", override=True)

def parse_args():
    parser = argparse.ArgumentParser(description="Run the ReAct CCRS Agent")

    parser.add_argument("--recursion-limit", type=int, help="Override recursion limit")
    parser.add_argument("--agent-name", type=str, help="Name of the agent run")
    parser.add_argument("--log-level", type=str, help="Logging level")
    parser.add_argument("--query", type=str, help="User query")
    parser.add_argument("--graph-name", type=str, default="graph", help="Name of the graph module to use (default: graph)")
    parser.add_argument("--run-mode", type=str, choices=["sync", "async"], help="Execution mode")
    parser.add_argument(
        "--llm-message-window-max-messages",
        type=int,
        help="Maximum recent non-preserved messages sent through the LLM message history window",
    )
    parser.add_argument(
        "--llm-message-window-max-tokens",
        type=int,
        help="Maximum approximate tokens for non-preserved messages sent through the LLM message history window",
    )
    parser.add_argument(
        "--enable-contingency-escalation-tool",
        action="store_true",
        help="Expose the opt-in escalate_to_contingency_ccrs tool when using graph_ccrs",
    )
    parser.add_argument(
        "--enable-contingency-llm-prediction",
        action="store_true",
        help="Enable the optional Java contingency LLM prediction capability when using graph_ccrs",
    )
    parser.add_argument(
        "--enable-contingency-a2a-consultation",
        action="store_true",
        help="Enable the optional Java contingency A2A consultation capability when using graph_ccrs",
    )
    parser.add_argument(
        "--contingency-ccrs-modules",
        type=str,
        help=(
            "Comma- or space-separated Java CCRS modules for contingency evaluation, "
            f"for example: {CCRS_CORE_MODULE},{CCRS_LANGCHAIN4J_MODULE},{CCRS_A2A_MODULE}"
        ),
    )
    parser.add_argument(
        "--discover-contingency-strategy-providers",
        action="store_true",
        help="Discover Java contingency strategy providers with ServiceLoader when using graph_ccrs",
    )
    parser.add_argument(
        "--sync-contingency-llm-model",
        action="store_true",
        help="Set OPENAI_MODEL from the Python agent llm_model before constructing Java contingency providers",
    )

    return parser.parse_args()


def main():
    # Parse command-line arguments
    args = parse_args()

    # Define the query
    query = args.query or USER_QUERY
    if args.sync_contingency_llm_model:
        os.environ.setdefault("OPENAI_MODEL", settings.llm_model)
    message_window_kwargs = {}
    if args.llm_message_window_max_messages is not None:
        message_window_kwargs["llm_message_window_max_messages"] = args.llm_message_window_max_messages
    if args.llm_message_window_max_tokens is not None:
        message_window_kwargs["llm_message_window_max_tokens"] = args.llm_message_window_max_tokens

    # Launch the agent
    asyncio.run(launch_agent(
        query=query,
        agent_name=args.agent_name,
        graph_name=args.graph_name,
        recursion_limit=args.recursion_limit,
        log_level=args.log_level,
        run_mode=args.run_mode,
        enable_contingency_escalation_tool=args.enable_contingency_escalation_tool,
        enable_contingency_llm_prediction=args.enable_contingency_llm_prediction,
        enable_contingency_a2a_consultation=args.enable_contingency_a2a_consultation,
        contingency_ccrs_modules=args.contingency_ccrs_modules,
        discover_contingency_strategy_providers=args.discover_contingency_strategy_providers,
        **message_window_kwargs,
    ))


if __name__ == "__main__":
    main()
