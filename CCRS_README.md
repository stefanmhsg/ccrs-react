# CCRS Integration Direction

This document describes the intended direction for using the Java CCRS
libraries from this Python ReAct/LangGraph agent project. It is deliberately a
living design and progress document. It records the current implementation
direction, open decisions, cleanup candidates, and conventions that should be
preserved across multiple Codex sessions.

## Source Of The CCRS Libraries

The reusable CCRS implementation lives in the sibling
[ccrs-bdi repository](../ccrs-bdi/README.md). That repository currently serves
two roles:

- it is the source and publishing workspace for the reusable `ccrs-*` Java
  libraries;
- it also contains a JaCaMo/Jason user application that uses those modules
  directly through Gradle project dependencies.

For this Python project, the relevant part is the publishable Java libraries:

- [ccrs-core](../ccrs-bdi/ccrs-core)
- [ccrs-jacamo](../ccrs-bdi/ccrs-jacamo)
- [ccrs-hypermedea](../ccrs-bdi/ccrs-hypermedea)
- [ccrs-langchain4j](../ccrs-bdi/ccrs-langchain4j)
- [ccrs-a2a](../ccrs-bdi/ccrs-a2a)

The expected first distribution target is local Maven. From
[../ccrs-bdi](../ccrs-bdi/README.md), publish the libraries with:

```powershell
./gradlew publishToMavenLocal
```

The local Maven coordinates use:

```text
io.github.stefanmhsg.ccrs:<module-name>:0.1.0-SNAPSHOT
```

For example:

```text
io.github.stefanmhsg.ccrs:ccrs-core:0.1.0-SNAPSHOT
```

Local Maven is not the final Python integration by itself. It is the local
artifact source from which this project can load or assemble the Java CCRS
runtime once the Python/JVM boundary is chosen.

## Why CCRS Needs Runtime Integration

CCRS is not meant to be a loose external advisor. It is an agent-agnostic set
of runtime strategies for opportunistic CCRS and contingency CCRS. Its useful inputs
come from the running agent:

- current and recent RDF observations;
- current resource or focus;
- recent tool calls and HTTP interactions;
- action failures and error details;
- trace history from previous CCRS evaluations;
- agent identity and, later, possible consultation channels.

That means the Python agent must expose parts of its state and loop to CCRS.
The intended architecture is tight runtime integration, not a separate HTTP
service that receives occasional summaries.

## Current Python ReAct Shape

The baseline graph is defined in [react_agent/graph/graph.py](react_agent/graph/graph.py).
The current CCRS-oriented graph is
[react_agent/graph/graph_opportunistic_ccrs.py](react_agent/graph/graph_opportunistic_ccrs.py):

```text
llm -> tools -> opportunistic_ccrs -> llm
```

The CCRS state in
[react_agent/ccrs/state.py](react_agent/ccrs/state.py)
adds an append-only `ccrs` channel beside the normal message list:

```text
messages
number_of_cycles
ccrs
```

The current opportunistic CCRS node,
[react_agent/ccrs/opportunistic.py](react_agent/ccrs/opportunistic.py), parses
the latest textual tool response as Turtle with `rdflib`, converts the RDF
batch to Java `RdfTriple` values, and calls Java
`VocabularyMatcher.scanAll(...)` through a JPype in-process JVM.

The CCRS-aware LLM node,
[react_agent/nodes/llm_node_ccrs_v2.py](react_agent/nodes/llm_node_ccrs_v2.py),
filters CCRS entries to the latest tool call IDs and injects those entries into
the CCRS-specific ReAct prompt from
[react_agent/prompts/react_prompt.py](react_agent/prompts/react_prompt.py).

This graph shape gives CCRS a stable observation point where derived
course-check information can be produced and fed into the next reasoning step.
The baseline ReAct graph remains CCRS-free: it uses
[react_agent/state/state.py](react_agent/state/state.py),
[react_agent/nodes/llm_node.py](react_agent/nodes/llm_node.py), and the plain
`react_prompt` without any CCRS state keys or prompt variables.

## Intended Role Of The Java CCRS Libraries

The current implementation path replaces hand-coded Python CCRS extraction
with the Java CCRS runtime from the published Maven artifacts.

At a conceptual level:

- opportunistic CCRS should interpret RDF observations and produce reusable
  course-check annotations instead of hard-coded checks for one predicate;
- contingency CCRS should evaluate failures, stuck states, uncertainty, and
  proactive checks using reusable strategy objects;
- CCRS trace history should be preserved as runtime evidence for future
  strategy selection;
- ReAct decisions should be informed by CCRS results before the next action is
  selected;
- tool failures should become structured CCRS situations rather than only text
  for the next LLM call.

The Java CCRS core should remain agent-agnostic. This Python project should own
the Python-specific adapter that maps LangGraph state, messages, tool calls,
and RDF observations into the CCRS contracts.

## Conceptual Integration Points

The likely integration points in this ReAct project are:

| Agent point | CCRS role |
| --- | --- |
| after `tools` | inspect tool responses, especially Turtle observations and error results |
| before the next `llm` step | provide opportunistic CCRS annotations or contingency CCRS suggestions to the decision step |
| on tool failure | construct a structured failure situation for contingency strategies |
| while maintaining state | expose recent RDF memory, current focus, interaction history, and CCRS traces |
| after executing a contingency CCRS suggestion | record whether the suggestion helped |

These are conceptual integration points only. JPype is now the selected
Python/JVM bridge, but the broader state schema, retained object lifetimes, and
control policy still need to be refined as the adapter evolves.

## Non-Goals

- Do not call CCRS as a separate HTTP sidecar for normal loop decisions.
- Do not reduce CCRS to prompt text that the LLM has to simulate.
- Do not copy the JaCaMo adapter into Python. JaCaMo-specific classes are a
  reference for what an adapter must accomplish, not the adapter for this
  project.
- Do not decide here whether CCRS suggestions are advisory-only or allowed to
  override/control the next ReAct action.

## Open Design Questions

The next design step is to refine the Python integration boundary. In
particular:

- how robust the JPype Maven-local classpath resolver should be;
- how Python state should expose the CCRS context contract;
- how RDF memory should be represented and retained across graph cycles;
- how tool request/response history should be captured;
- how contingency suggestions should be handed back to the ReAct loop;
- how CCRS trace outcomes should be reported;
- which optional CCRS modules should be in scope first.

Those decisions should be settled incrementally as the adapter moves from the
first opportunistic CCRS integration toward reusable contingency CCRS support.

## Working Direction: Reusable Python ReAct Adapter

The intended Python integration should mirror the role of `ccrs-jacamo` in the
sibling Java workspace: it should be an adapter and glue-code layer for one
agent runtime, not a copy of CCRS logic.

The working target is a reusable Python adapter for ReAct/LangGraph agents:

```text
ccrs-core              Java agent-agnostic CCRS logic
ccrs-jacamo            Java adapter for JaCaMo/Jason agents
ccrs-react-python      Python adapter for LangGraph/ReAct agents
```

The Python adapter should own the mapping between LangGraph state, LangChain
messages, Python tools, RDF observations, and the Java CCRS contracts. The Java
`ccrs-core` module should remain the source of opportunistic and contingency
strategy behavior.

### Adapter Responsibilities

The reusable adapter layer should package the responsibilities that every
Python ReAct integration would otherwise have to reimplement:

- runtime wiring for loading the Java CCRS artifacts from local Maven through
  JPype;
- RDF conversion between `rdflib` graphs, Turtle tool responses, and Java
  `RdfTriple` values;
- conversion of Java opportunistic CCRS results into stable Python dictionaries
  suitable for the LangGraph `ccrs` state channel;
- a ready-made LangGraph opportunistic CCRS node from
  [react_agent/ccrs/opportunistic.py](react_agent/ccrs/opportunistic.py);
- state helpers for CCRS annotations, RDF memory, interaction history, trace
  history, and current-resource tracking;
- prompt-formatting helpers for injecting CCRS context into prompts such as
  [react_agent/prompts/react_prompt.py](react_agent/prompts/react_prompt.py);
- optional wrappers for Python tools so HTTP requests, responses, failures,
  timing, and RDF observations can become structured CCRS context;
- later contingency CCRS integration for tool failures, stuck states,
  uncertainty, and proactive checks;
- a minimal public API so a plain ReAct/LangGraph agent can opt in with one or
  two imports rather than hand-written bridge code.

The adapter boundary must not leak into the baseline ReAct implementation.
Baseline modules should not import `react_agent.ccrs`, should not initialize a
`ccrs` state key, and should not pass CCRS prompt variables. CCRS behavior
belongs in CCRS graph/state/node/prompt variants or in the reusable adapter
package.

### Suggested Package Shape

A first implementation can live inside this repository while the adapter
boundary stabilizes:

```text
react_agent/ccrs/
  runtime.py          # starts/configures the JPype JVM
  rdf_adapter.py      # rdflib/Turtle <-> Java RdfTriple conversion
  opportunistic.py    # LangGraph opportunistic CCRS node factory
  state.py            # CCRS-oriented state helpers
  prompting.py        # formatting/filtering helpers for LLM injection
  tools.py            # optional HTTP tool wrappers and history capture
  contingency.py      # later Java ContingencyCcrs wrapper
  __init__.py         # compact public imports for application code
  README.md           # package intent, file roles, naming/logging notes
```

Every new package directory added for CCRS integration should include a
`README.md` that explains the package purpose, current scope, public entry
points, and any naming or logging conventions that package must preserve.

If the adapter becomes useful outside this project, it should be split into a
separate package, for example `ccrs-react-python` or `ccrs-langgraph`, with
this repository consuming it as a normal dependency.

### Java Boundary: JPype In-Process JVM

The selected bridge direction is JPype with an in-process JVM. The adapter
should discard the long-lived stdio bridge and one-shot CLI alternatives for
normal runtime integration.

JPype fits the target architecture because it:

- keeps Java opportunistic CCRS and contingency CCRS objects alive across graph
  cycles;
- preserves runtime CCRS vocabulary discovery in the same Java object lifetime;
- avoids an HTTP sidecar for normal loop decisions;
- avoids process-per-observation startup cost;
- lets Python expose ready-made LangGraph nodes while still using Java
  `ccrs-core` as the implementation source.

The adapter should hide JPype details from application code. Application code
should not manually start the JVM, assemble Java classpaths, instantiate Java
`VocabularyMatcher` objects, or convert Java collections. Those details belong
inside `react_agent/ccrs/` first and later inside the reusable adapter package.

A separate Java facade or shaded bridge jar is not part of the current plan.
It would add another abstraction before the JPype integration has shown a real
need for one. Revisit that idea only if direct JPype access to the published
Maven artifacts creates concrete packaging or classpath problems that the
Python adapter cannot reasonably hide.

The initial JPype runtime should load `ccrs-core` from the local Maven
repository and resolve the classpath in one adapter-owned place. If classpath
resolution becomes awkward, prefer improving the Python runtime loader before
introducing a new Java module.

### First Milestone

The first reusable slice should focus only on opportunistic CCRS:

```text
Python ToolMessage Turtle
-> rdflib triples
-> Java ccrs-core VocabularyMatcher.scanAll(...)
-> Python CCRS annotation dictionaries
-> existing ccrs state channel
-> next ReAct LLM prompt
```

This milestone replaced the earlier hard-coded `maze:green` logic with
Java-backed vocabulary scanning while keeping the current runnable graph module
in [react_agent/graph/graph_opportunistic_ccrs.py](react_agent/graph/graph_opportunistic_ccrs.py).

A target usage sketch for this repository is:

```python
from react_agent.ccrs import opportunistic_ccrs_node

# Use opportunistic_ccrs_node directly in the graph after tools.
```

For applications that need explicit configuration, the adapter can still expose
a slightly longer form:

```python
from react_agent.ccrs import CcrsRuntime, make_opportunistic_ccrs_node

opportunistic_ccrs_node = make_opportunistic_ccrs_node(
    CcrsRuntime.from_maven_local(version="0.1.0-SNAPSHOT")
)
```

New code should use `make_opportunistic_ccrs_node(...)` and
`opportunistic_ccrs_node`.

### Naming, Logging, And Comment Rules

Use consistent CCRS approach names in code comments, documentation, and log
messages:

- Use `opportunistic CCRS` for RDF-derived course-check annotations produced
  from observations.
- Use `contingency CCRS` for CCRS behavior that evaluates failures, stuck
  states, uncertainty, or proactive checks.
- Do not use `observation`, `scanner`, `error handling`, or `recovery` as
  replacement names for the CCRS approach. Those terms may describe local
  implementation details only after the approach name is clear.

Logging rules:

- Every Python log line emitted for opportunistic CCRS behavior must begin with
  `[Opportunistic CCRS]`.
- Future contingency CCRS logs must begin with `[Contingency CCRS]`.
- Log enough detail to reconstruct the CCRS path: runtime/classpath setup,
  Turtle parsing, RDF triple counts, Java CCRS invocation, Java result counts,
  result conversion, and any skipped evaluation reason.
- Prefer logging context values such as `tool_call_id`, `tool_name`,
  `content_length`, triple count, and result count.
- The Java CCRS libraries also emit detailed logs through Java logging. The
  Python adapter should preserve and, where practical, route those logs into
  the Python logging output so one run log contains both adapter-level and
  Java-library CCRS traces.
- Current status: the JPype runtime configures Java CCRS logger levels to be
  verbose. A dedicated Java-to-Python logging bridge is still a follow-up if
  Java library messages do not appear in the Python run log.

Comment rules:

- Add concise comments or docstrings at adapter boundaries where the relation
  to CCRS is otherwise not obvious.
- Comments should state the key element and purpose, for example why a node is
  the opportunistic CCRS integration point or why Java objects are retained
  across graph cycles.
- Avoid broad narrative comments when the function name and local code already
  make the purpose clear.

### Notebook Run Matrix

[test_agent.ipynb](test_agent.ipynb) is the easy-to-run workspace for available
implementation variants. Keep it as a maintained notebook that uses
[react_agent/api.py](react_agent/api.py) with predefined run configurations for
the baseline graph, opportunistic CCRS graph, and future contingency CCRS
variants. Do not treat notebook changes as disposable cleanup; review and
update them deliberately whenever graph names, public adapter imports, or run
configuration defaults change.

### Legacy And Cleanup Candidates

These items are kept for compatibility or generated context and can be cleaned
up after confirmation:

| Item | Current role | Cleanup direction |
| --- | --- | --- |
| Generated graph images | Runtime-generated graph visualizations. | Regenerate by running the desired graph through [react_agent/api.py](react_agent/api.py); do not keep stale generated images for removed graph modules. |

Completed cleanup:

- Removed deprecated `react_agent/ccrs/observation.py`.
- Removed deprecated `react_agent/nodes/ccrs_observation_node_v2.py`.
- Removed deprecated `react_agent/state/state_ccrs_v2.py`.
- Updated the active opportunistic CCRS graph to import `CcrsAgentState` and
  `opportunistic_ccrs_node` directly from [react_agent/ccrs](react_agent/ccrs).
- Renamed the graph node label from `ccrs_observation` to
  `opportunistic_ccrs`.
- Replaced prototype graph module `graph_ccrs_v2` with
  [react_agent/graph/graph_opportunistic_ccrs.py](react_agent/graph/graph_opportunistic_ccrs.py).
- Removed stale generated `graph_ccrs_v2.png`.

### Progress Tracker

- [x] Python graph has a CCRS observation point after tool execution.
- [x] Python state has an append-only `ccrs` channel.
- [x] Prototype observation node proved the Turtle-to-CCRS observation slot.
- [x] Local Maven artifacts for the `ccrs-*` modules are available.
- [x] Choose JPype as the Python/JVM bridge mechanism.
- [x] Add a small Python adapter package under `react_agent/ccrs/`.
- [x] Replace hard-coded Python signifier extraction with Java
  `VocabularyMatcher.scanAll(...)`.
- [x] Hide JVM startup, Maven-local classpath resolution, and Java object
  conversion behind compact Python imports.
- [x] Add [react_agent/ccrs/README.md](react_agent/ccrs/README.md) for the new
  adapter package.
- [x] Add naming, logging, comment, and cleanup rules to this living document.
- [ ] Install JPype in the active Python environment and verify a real
  Java-backed scan against a Turtle observation.
- [ ] Route Java CCRS library logs into the Python log output if direct JPype
  integration does not already preserve enough Java logging context.
- [ ] Preserve RDF memory across graph cycles.
- [ ] Capture structured HTTP interaction history from Python tools.
- [ ] Add contingency CCRS evaluation for tool failures.
- [ ] Decide whether the adapter should be published as a separate reusable
  package.
