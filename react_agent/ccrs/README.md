# CCRS ReAct Adapter

This package contains the Python adapter layer that equips LangGraph/ReAct
agents with CCRS behavior while keeping the Java CCRS libraries as the source
of the CCRS concepts and strategy implementations.

The baseline ReAct graph is intentionally free of CCRS imports, CCRS state
keys, and CCRS prompt variables. Use this package only from CCRS-specific graph
variants such as [graph_ccrs.py](../graph/graph_ccrs.py).

For the broader CCRS concept, start with
[CCRS_LIBRARY.md](../../../ccrs-bdi/CCRS_LIBRARY.md). It focuses on BDI agents
and the JaCaMo adapter, but it explains the generic CCRS intention and points
to further resources. The Java behavior most directly relevant to this adapter
is documented in the opportunistic CCRS
[README.md](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/opportunistic/README.md)
and contingency CCRS
[README.md](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/README.md).

The active implementation plan for this package is
[PLAN_CCRS_README.md](../../PLAN_CCRS_README.md).

## Adapter Role

The adapter has three responsibilities:

1. Convert React/LangGraph data into Java CCRS inputs.
2. Call Java CCRS library entry points through JPype.
3. Convert Java CCRS outputs into normal LangGraph state and prompt context.

The adapter should not redefine CCRS semantics in Python. Python code may decide
how a React agent exposes tool messages, state, routing, and prompt injection,
but CCRS matching, contingency strategy evaluation, strategy selection, and
optional Java capabilities remain Java-library concerns.

## Concept Map

| CCRS library concept | React adapter element | Purpose in the React agent |
| --- | --- | --- |
| Java [RdfTriple.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/rdf/RdfTriple.java) | [rdf_adapter.py](rdf_adapter.py) | Parses Turtle tool-message bodies and converts RDF triples into Java-compatible values. |
| Java [VocabularyMatcher.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/opportunistic/VocabularyMatcher.java) | [opportunistic/vocabulary_matcher.py](opportunistic/vocabulary_matcher.py) | Runs opportunistic CCRS matching over the latest parseable tool observation. |
| Java [OpportunisticResult.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/opportunistic/OpportunisticResult.java) | [opportunistic/opportunistic_result.py](opportunistic/opportunistic_result.py) | Represents opportunistic annotations and selects entries relevant to the latest LLM tool calls. |
| Java [Situation.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/dto/Situation.java) | [contingency/situation.py](contingency/situation.py) | Provides the Python input shape for contingency CCRS evaluation. |
| Java [CcrsContext.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/rdf/CcrsContext.java) | [contingency/ccrs_context.py](contingency/ccrs_context.py) | Exposes agent id, current resource, interaction history, RDF query support, and trace history to Java strategies. |
| Java [Interaction.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/dto/Interaction.java) | [contingency/interaction.py](contingency/interaction.py) | Normalizes parseable tool messages into interaction records for contingency context queries. |
| Java [InMemoryCcrsTraceHistory.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/rdf/InMemoryCcrsTraceHistory.java) | [contingency/in_memory_ccrs_trace_history.py](contingency/in_memory_ccrs_trace_history.py) | Stores contingency invocation traces across CCRS cycles in the same graph execution. |
| Java [ContingencyCcrs.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/ContingencyCcrs.java) | [contingency/contingency_ccrs.py](contingency/contingency_ccrs.py) | Calls Java contingency strategy evaluation and converts the resulting trace into Python dictionaries. |
| Java [StrategyResult.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/dto/StrategyResult.java) and [CcrsTrace.java](../../../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/dto/CcrsTrace.java) | [contingency/contingency_ccrs_result.py](contingency/contingency_ccrs_result.py) | Selects pending contingency outputs for one-shot prompt injection and marks them completed after the LLM sees them. |
| Opportunistic guidance emitted by contingency strategies | [contingency/opportunistic_guidance.py](contingency/opportunistic_guidance.py) | Holds replaceable guidance from the latest contingency evaluation and reveals it only when its target appears in the latest RDF tool response. |
| React graph-control policy | [contingency/escalation.py](contingency/escalation.py), [contingency/default_escalation_controller.py](contingency/default_escalation_controller.py), and [contingency/decision.py](contingency/decision.py) | Decides when to construct a `Situation`, routes to `ccrs_node`, and keeps graph-control policy separate from Java contingency execution. |

## Graph Integration

The CCRS graph entry point is [graph_ccrs.py](../graph/graph_ccrs.py). It wires
the LLM node, decision node, tool node, and CCRS node together.

The graph-facing CCRS node import is:

```python
from react_agent.ccrs.ccrs_node import make_ccrs_node
```

[ccrs_node.py](ccrs_node.py) is the unifying graph node. It imports concrete
functions and wrappers from the opportunistic and contingency subpackages and
returns LangGraph state updates.

The CCRS graph variant follows this shape:

```text
LLM node
-> decision node
-> tool node
-> CCRS node
-> LLM node
```

On every pass, the CCRS node tries opportunistic CCRS first:

```text
latest ToolMessage
-> parse Turtle body
-> convert to Java RdfTriple values
-> Java VocabularyMatcher.scanAll(...)
-> append opportunistic_ccrs entries
```

If graph control supplies a `contingency_situation`, the same CCRS node also
runs contingency CCRS. The normal escalation route is:

```text
LLM node
-> decision node
-> CCRS node
-> LLM node
```

The CCRS decision node is provided by
[contingency/decision.py](contingency/decision.py). It calls
`decide_contingency_ccrs_escalation(...)` from
[contingency/escalation.py](contingency/escalation.py), using the default
policy in
[contingency/default_escalation_controller.py](contingency/default_escalation_controller.py)
unless a graph or run config supplies a custom controller. Explicit LLM requests
through the opt-in `escalate_to_contingency_ccrs` tool take precedence over
default controller-derived escalation, so only one situation is created for a
graph cycle.

[graph_ccrs.py](../graph/graph_ccrs.py) owns tool binding for the CCRS graph.
When `enable_contingency_escalation_tool=True`, the graph adds
`escalate_to_contingency_ccrs` to the tools passed into
[llm_node_ccrs_v2.py](../nodes/llm_node_ccrs_v2.py). The LLM node itself only
binds the graph-provided tool list.

The CLI exposes that graph-build option as:

```powershell
python main.py --graph-name graph_ccrs --enable-contingency-escalation-tool --agent-name "CCRSAgent" --log-level "DEBUG"
```

The contingency execution path is:

```text
contingency_situation
-> Python Situation
-> Java Situation
-> Java CcrsContext proxy
-> Java ContingencyCcrs.evaluateWithTrace(...)
-> append contingency_ccrs result
-> replace opportunistic_guidance_by_contingency_ccrs
```

Package C in [PLAN_CCRS_README.md](../../PLAN_CCRS_README.md) decides when a
React graph should supply `contingency_situation`. Package D owns the node-side
implementation once that situation exists.

## State Channels

[state.py](state.py) defines the CCRS-aware LangGraph state shape. The current
adapter intentionally keeps the state surface small:

| State key | Lifecycle | Prompt surfacing |
| --- | --- | --- |
| `opportunistic_ccrs` | Append-only opportunistic annotations produced from tool observations. | Injected when an entry's `tool_call_id` matches the latest LLM tool call ids. |
| `contingency_ccrs` | Append-only contingency traces/results. Entries without `completed=True` are pending. | Injected once in the next LLM node call, then marked completed through the reducer. |
| `opportunistic_guidance_by_contingency_ccrs` | Replaceable channel produced by the latest contingency evaluation. A new contingency evaluation replaces the whole channel. | Injected when a guidance `target` appears exactly as an RDF subject or object in the latest parseable tool response. |
| `contingency_situation` | Transient input that asks the CCRS node to run contingency evaluation. | Not prompt-injected directly; consumed by `ccrs_node` and then cleared. |

The trace-history object used by contingency CCRS must survive across CCRS
cycles in the same graph execution. This allows retry limits, stop exhaustion,
and trace-based strategy selection to observe previous contingency invocations.

## Prompt Surface

[prompt_context.py](prompt_context.py) gathers all prompt-visible CCRS context
into one JSON payload. [llm_node_ccrs_v2.py](../nodes/llm_node_ccrs_v2.py)
passes that JSON through the existing `{ccrs}` placeholder in
[react_prompt.py](../prompts/react_prompt.py).

The current payload keys are:

- `opportunistic_annotations`
- `contingency_ccrs`
- `opportunistic_guidance_by_contingency_ccrs`

[prompt.py](prompt.py) owns the default CCRS system prompt fragment.
[react_prompt.py](../prompts/react_prompt.py) owns the agent prompt and exposes
`make_react_prompt_ccrs(...)`, which accepts an overridable CCRS system prompt.
[graph_ccrs.py](../graph/graph_ccrs.py) can also pass a complete custom prompt
template into the CCRS LLM node through `ccrs_prompt_template`.

The prompt template intentionally keeps one `{ccrs}` placeholder for now.
Future work can split prompt placeholders by CCRS type if the current JSON
payload needs stronger type-specific wording.

## Module Map

Shared adapter modules:

- [ccrs_node.py](ccrs_node.py) coordinates graph-facing opportunistic and
  contingency CCRS updates.
- [state.py](state.py) defines the reusable CCRS-aware LangGraph state channels
  and reducers.
- [rdf_adapter.py](rdf_adapter.py) parses Turtle and prepares RDF triples for
  Java calls.
- [java_runtime.py](java_runtime.py) resolves Maven/Gradle classpaths, starts
  JPype, and loads Java classes.
- [java_logging.py](java_logging.py) configures Java `java.util.logging` output
  into per-run companion log files.
- [prompt.py](prompt.py) provides the default CCRS system prompt fragment.
- [prompt_context.py](prompt_context.py) renders the prompt-visible CCRS JSON
  payload and returns post-LLM completion updates.
- [audit.py](audit.py) emits stable React adapter event logs for experiment
  inspection.

Opportunistic CCRS modules:

- [opportunistic/vocabulary_matcher.py](opportunistic/vocabulary_matcher.py)
  wraps Java `VocabularyMatcher`, evaluates the latest tool observation, and
  converts Java opportunistic results to Python dictionaries.
- [opportunistic/opportunistic_result.py](opportunistic/opportunistic_result.py)
  selects opportunistic entries for prompt injection by latest tool-call id.

Contingency CCRS modules:

- [contingency/escalation.py](contingency/escalation.py) provides
  `decide_contingency_ccrs_escalation(...)`, the controller protocol, decision
  result, and the opt-in `escalate_to_contingency_ccrs` tool.
- [contingency/default_escalation_controller.py](contingency/default_escalation_controller.py)
  contains the conservative default policy for explicit LLM escalation and
  repeated tool invocation failures.
- [contingency/decision.py](contingency/decision.py) provides CCRS graph routing
  helpers that keep baseline decision routing free of CCRS imports.
- [contingency/contingency_ccrs.py](contingency/contingency_ccrs.py) wraps Java
  `ContingencyCcrs`, handles optional Java provider discovery, records traces,
  and converts Java results into Python dictionaries.
- [contingency/situation.py](contingency/situation.py) mirrors Java
  `Situation` input fields.
- [contingency/ccrs_context.py](contingency/ccrs_context.py) provides the Java
  `CcrsContext` proxy backed by parseable React tool messages and trace
  history.
- [contingency/interaction.py](contingency/interaction.py) maps tool messages
  into interaction records for the context.
- [contingency/in_memory_ccrs_trace_history.py](contingency/in_memory_ccrs_trace_history.py)
  mirrors Java trace-history method names and keeps invocation traces available
  across CCRS cycles.
- [contingency/contingency_ccrs_result.py](contingency/contingency_ccrs_result.py)
  manages pending/completed contingency prompt injection.
- [contingency/opportunistic_guidance.py](contingency/opportunistic_guidance.py)
  extracts and target-matches opportunistic guidance produced by contingency
  strategies.

[__init__.py](__init__.py) only marks the package. Adapter code should import
from concrete modules instead of relying on root-package re-exports.

## Java Capabilities

The default contingency wrapper loads `ccrs-core` only. Optional Java capability
modules can be made visible through the JPype classpath and discovered by Java
`ServiceLoader`.

For Java-backed LLM prediction strategies:

```python
from react_agent.ccrs.contingency.contingency_ccrs import ContingencyCcrs

contingency_ccrs = ContingencyCcrs.from_maven_local(
    modules=("ccrs-core", "ccrs-langchain4j"),
    discover_strategy_providers=True,
)
```

For A2A consultation strategies, include the A2A module as well:

```python
contingency_ccrs = ContingencyCcrs.from_maven_local(
    modules=("ccrs-core", "ccrs-langchain4j", "ccrs-a2a"),
    discover_strategy_providers=True,
)
```

The React adapter does not provide its own Python LLM client for Java
contingency strategies. Java strategy providers should use the Java capability
configuration supplied by the CCRS Maven libraries.

## Logging And Naming

React-side human-readable CCRS log lines use prefixes such as
`[React CCRS][Opportunistic]` and `[React CCRS][Contingency]`. Auditable
lifecycle events use the React-adapter-specific `[REACT-CCRS-EVENT]` prefix.
Java library events can continue using `[CCRS-EVENT]`.

Important React opportunistic event names:

- `react.ccrs.opportunistic.evaluate`
- `react.ccrs.opportunistic.detected`
- `react.ccrs.opportunistic.cycle_annotations`
- `react.ccrs.opportunistic.no_annotations`
- `react.ccrs.opportunistic.skipped`
- `react.ccrs.opportunistic.failed`

Invalid or non-RDF tool output should be logged as
`react.ccrs.opportunistic.skipped reason=invalid_turtle`, not as a CCRS runtime
failure. This is expected for raw tool responses that are not Turtle
observations.

Important React contingency event names:

- `react.ccrs.contingency.escalation.considered`
- `react.ccrs.contingency.escalation.activated`
- `react.ccrs.contingency.escalation.skipped`
- `react.ccrs.contingency.classpath.resolved`
- `react.ccrs.contingency.jvm.start`
- `react.ccrs.contingency.runtime.ready`
- `react.ccrs.contingency.evaluate`
- `react.ccrs.contingency.returned`

Important contingency-produced opportunistic guidance event names:

- `react.ccrs.opportunistic_guidance_by_contingency_ccrs.matched`
- `react.ccrs.opportunistic_guidance_by_contingency_ccrs.no_match`
- `react.ccrs.opportunistic_guidance_by_contingency_ccrs.skipped`

If the React run log is `logs/<run>.log`, Java CCRS library messages are
written to the companion file `logs/<run>.java.log`. The companion file uses
the `[JAVA-CCRS]` prefix and captures Java library events such as vocabulary
loading, pattern compilation, matches, warnings, and Java-side `[CCRS-EVENT]`
records. Keeping Java logs in a companion file avoids cross-runtime file
handler conflicts while preserving the same run name for experiment analysis.

Use the names `opportunistic CCRS` and `contingency CCRS` consistently when
describing CCRS approaches. Terms such as observation node, scanner, error
handling, or recovery may describe implementation details, but they should not
replace the CCRS approach name in user-facing documentation or logs.
