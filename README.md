# React Agent

## Configurations (Graphs)

[graph](react_agent/graph/graph.py) - Basic graph configuration without CCRS-specific nodes.

[graph_ccrs](react_agent/graph/graph_ccrs.py) - Graph configuration with CCRS.

## Run

Can be run either via the commandline tool or the notebook.

### Install dependencies

```powershell
python -m pip install -r requirements.txt
```

For opportunistic CCRS, see the React adapter notes in
[react_agent/ccrs/README.md](react_agent/ccrs/README.md).

### Notebook

[Notebook](./test_agent.ipynb)

Use the notebook as the maintained easy-to-run place for predefined agent run
configurations and implementation variants, including the baseline graph,
opportunistic CCRS graph, and future contingency CCRS variants.

### Commandline tool

```powershell
python main.py --graph-name graph_ccrs --agent-name "CCRSAgent" --log-level "DEBUG"
```

Expose the optional LLM self-escalation tool for contingency CCRS:

```powershell
python main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --agent-name "CCRSAgent" --log-level "DEBUG"
```

Enable optional Java contingency providers from the CLI:

```powershell
python main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --enable-contingency-llm-prediction --sync-contingency-llm-model --agent-name "CCRSAgent" --log-level "DEBUG"
```

For A2A consultation as well:

```powershell
python main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --enable-contingency-llm-prediction --enable-contingency-a2a-consultation --sync-contingency-llm-model --agent-name "CCRSAgent" --log-level "DEBUG"
```

Options

    --agent-name            (default: "React")

    --log-level             Logging level (default: "INFO")

    --run-mode              sync or async (default: "sync")

    --graph-name            (default: "graph")

    --recursion-limit       Override recursion limit

    --query                 (default: Maze Prompt)

    --llm-message-window-max-messages
                            Maximum recent non-preserved messages sent through the LLM message history window

    --llm-message-window-max-tokens
                            Maximum approximate tokens for non-preserved messages sent through the LLM message history window

    --enable-contingency-escalation-tool
                            Expose the opt-in escalate_to_contingency_ccrs tool when using graph_ccrs

    --contingency-http-error-threshold
                            Consecutive HTTP status >= 400 tool responses before default contingency escalation

    --enable-contingency-llm-prediction
                            Enable the optional Java contingency LLM prediction capability when using graph_ccrs

    --enable-contingency-a2a-consultation
                            Enable the optional Java contingency A2A consultation capability when using graph_ccrs

    --contingency-ccrs-modules
                            Comma- or space-separated Java CCRS modules for contingency evaluation,
                            for example: ccrs-core,ccrs-langchain4j,ccrs-a2a

    --discover-contingency-strategy-providers
                            Discover Java contingency strategy providers with ServiceLoader when using graph_ccrs

    --sync-contingency-llm-model
                            Set OPENAI_MODEL from the Python agent llm_model before constructing Java contingency providers

LLM settings such as model, temperature, reasoning effort, message-window
limits, and LangChain project are read from `.env` through
[settings.py](react_agent/utils/settings.py). The message window keeps the
first user query and trims only the message history passed through the prompt's
`MessagesPlaceholder`; system prompts and CCRS prompt text remain outside that
trimming scope. Configure `LLM_MESSAGE_WINDOW_MAX_MESSAGES` for message-count
trimming and `LLM_MESSAGE_WINDOW_MAX_TOKENS` for approximate token trimming.

## References

- [Google Gemini LangGraph Example](https://ai.google.dev/gemini-api/docs/langgraph-example)

> "LangGraph provides a convenient helper, add_messages, for updating message lists in the state. It functions as a reducer, meaning it takes the current list and new messages, then returns a combined list. It smartly handles updates by message ID and defaults to an "append-only" behavior for new, unique messages."

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)
