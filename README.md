# React Agent

## Configurations (Graphs)

[graph](react_agent/graph/graph.py) - Basic graph configuration without CCRS-specific nodes.

[graph_ccrs](react_agent/graph/graph_ccrs.py) - Graph configuration with CCRS.

## Run

Can be run either via the commandline tool or the notebook.

Automated experiment collection defaults to a supervised Python process through
[experiment_entry.py](experiment_entry.py), using the existing launch API and
settings extracted from the notebook. Follow the orchestration repository's
[Python execution guide](../ccrs-experiments/docs/GUIDED_REACT_PYTHON.md) for latest
wheel preparation, scenario-specific maze names, compact monitoring and evidence
collection. That flow loads .env before agent imports, preserves non-secret
effective settings and flushes tracing before process exit. The notebook remains
the maintained source of literal launch configurations and supports interactive runs.

For an authorized short trial, `launch_agent(..., max_iterations=3)` or
`main.py --max-iterations 3` stops before the fourth main ReAct loop. The first
three loops can complete their tool/CCRS work. This differs from recursion_limit,
which counts graph steps; contingency subcalls are not separate main loops.
The terminal event records iteration_limit, an intentional aborted execution.
An omitted limit leaves no explicit total-loop cap. The experiment stop budgets
below still apply. Experiment tooling sets trial limits
through init --max-iterations and has a separate process timeout.

Full runs leave max_iterations unset. The default recursion_limit is 100,000;
launch validation rejects insufficient graph-step headroom before graph/model
execution. With five zones and 1000 cycles per zone, the minimum is 15,100 steps
for baseline and 25,100 for CCRS. It is recalculated for custom zone budgets.
An explicit max_iterations selects a bounded trial and permits smaller execution
caps. CLI full runs also reject a leftover notebook max_iterations cap unless
the run explicitly requests that trial limit.

Full baseline and CCRS experiments also terminate after 50 agent-requested tool
invocations without a successful move to a different cell, or 1000 program cycles
without completing the current zone. Defaults and ordered boundaries are in
[experiment_stop_defaults.json](react_agent/experiment_stop_defaults.json).
[execution_control.py](react_agent/execution_control.py) maintains counters in
graph state. GETs, failed calls and CCRS escalation/confirmation calls count;
initial placement, self-posts and non-navigation interactions do not reset the
tool counter. A successful different-cell navigation POST resets it, including
on the 50th call. No subsequent call from that batch runs if the guard fires.

The first zone's budget starts at program cycle zero, including bootstrap.
Cycles use the existing state counter, including CCRS stop-confirmation cycles.
Zone completion resets the budget only upon first reaching the next ordered
boundary; movement within a zone and backtracking do not reset it. Reaching that
boundary on cycle 1000 is allowed. Both backends log no_movement_tool_limit or
zone_cycle_limit with counter/zone evidence and finish automatically. Python
tooling then verifies shutdown and follows its normal capture/report workflow.

### Install dependencies

```powershell
python -m pip install -r requirements.txt
```

The repository consumes the released `ccrs-langgraph` wheel through the first
entry in [requirements.txt](requirements.txt). To work against a sibling clone
of the adapter during development, install that clone explicitly:

```powershell
python -m pip install --no-deps -e ..\ccrs\ccrs-langgraph
```

For installation, GitHub Packages credentials, public APIs, and graph
integration, see the
[CCRS LangGraph adapter README.md](https://github.com/stefanmhsg/ccrs/blob/master/ccrs-langgraph/README.md).

The default CCRS runtime and optional contingency capabilities resolve Java
packages from GitHub Packages and refresh snapshot dependencies when a new
runtime is initialized. Restart the Python process or notebook kernel after
upgrading the wheel or refreshing Java packages to load the updated code.

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
