# React Agent

## Configurations (Graphs)

[graph](react_agent/graph.py) - Basic graph configuration without CCRS-specific nodes.

[graph_ccrs](react_agent/graph_ccrs.py) - Graph configuration with CCRS-specific nodes.

## Run

Can be run either via the commandline tool or the notebook.

### Notebook

[Notebook](./test_agent.ipynb)

### Commandline tool

```powershell
python main.py --graph-name graph_ccrs --agent-name "CCRSAgent" --log-level "DEBUG"
```

Options

    --agent-name            (default: "React")

    --log-level             Logging level (default: "INFO")

    --run-mode              sync or async (default: "sync")

    --graph-name            (default: "graph")

    --langchain-project     (default: "react")

    --llm-model             (default: "gpt-5-mini")

    --llm-temperature       (default: 1.0)

    --query                 (default: Maze Prompt)

## References

- [Google Gemini LangGraph Example](https://ai.google.dev/gemini-api/docs/langgraph-example)

> "LangGraph provides a convenient helper, add_messages, for updating message lists in the state. It functions as a reducer, meaning it takes the current list and new messages, then returns a combined list. It smartly handles updates by message ID and defaults to an "append-only" behavior for new, unique messages."

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)
