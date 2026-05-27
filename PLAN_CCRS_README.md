# PLAN_CCRS_README: Stabilize the CCRS ReAct Adapter Plan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

No repository-local `PLANS.md` or `.agent/PLANS.md` guide is currently checked in. This document follows the local `PLAN_<SCOPE>.md` convention and is intended to be self-contained enough for a future Codex session to resume CCRS adapter work without prior chat history.

## Purpose / Big Picture

The goal is to make the Python ReAct/LangGraph agent consume the reusable Java Course Check and Revision Strategy libraries through a small adapter layer. After this work, a user should be able to run the `graph_opportunistic_ccrs` graph, observe Java-backed opportunistic CCRS annotations in the LangGraph state, and verify the React adapter path through stable `[REACT-CCRS-EVENT]` audit log lines. The first deliverable is opportunistic CCRS only: RDF observations from tool messages are interpreted by Java `ccrs-core` and injected as advisory context into the next LLM decision. Contingency CCRS for failures, stuck states, retry, backtracking, and consultation remains future work.

## Progress

- [x] (2026-05-14) Added a `react_agent/ccrs/` package with runtime, RDF conversion, opportunistic node, CCRS state, and package README.
- [x] (2026-05-14) Replaced the older hard-coded Python `maze:green` extraction path with Java `ccrs.core.opportunistic.VocabularyMatcher.scanAll(...)` through JPype.
- [x] (2026-05-14) Replaced the prototype graph module with `react_agent/graph/graph_opportunistic_ccrs.py`, whose shape is `llm -> tools -> opportunistic_ccrs -> llm`.
- [x] (2026-05-26) Narrowed JPype classpath resolution from broad cache scanning to the CCRS module jar plus declared Jena runtime dependencies.
- [x] (2026-05-26) Verified a real Java-backed opportunistic scan with `S:\anaconda\agent\python.exe`, producing a `signifier` annotation for the default green vocabulary pattern.
- [x] (2026-05-27) Kept opportunistic CCRS state append-only and confirmed prompt injection filters by latest tool call IDs in `react_agent/nodes/llm_node_ccrs_v2.py`.
- [x] (2026-05-27) Replaced `number_of_cycles` with a single `cycle` state object containing `number` and UTC `timestamp`.
- [x] (2026-05-27) Added stable adapter audit events for opportunistic CCRS evaluation, detection, no-annotation, skipped, failed, runtime, and classpath events.
- [x] (2026-05-27) Renamed React adapter audit events to `[REACT-CCRS-EVENT] event=react.ccrs...` so they are distinguishable from Java library `[CCRS-EVENT] event=ccrs...` lines.
- [x] (2026-05-27) Classified invalid/non-RDF tool output as `react.ccrs.opportunistic.skipped reason=invalid_turtle` instead of an opportunistic CCRS evaluation failure.
- [ ] Add focused tests or smoke scripts for the adapter boundary so Java-backed scans and state merge behavior can be validated without a full LLM/maze run.
- [x] (2026-05-27) Updated root documentation links so `README.md` points to the React CCRS adapter documentation in `react_agent/ccrs/README.md` and this plan.
- [x] (2026-05-27) Established `react_agent/ccrs/README.md` as the React-specific CCRS documentation file while this file remains the executable implementation plan.
- [x] (2026-05-27) Added concise repository guidance in `AGENTS.md` for scope approval, plan usage, Decision Log highlighting, and CCRS conceptual starting points.
- [ ] Preserve RDF memory across graph cycles.
- [ ] Capture structured HTTP request/response/failure history from Python tools.
- [ ] Add contingency CCRS evaluation for tool failures after opportunistic CCRS is test-covered.
- [ ] Decide whether and when the adapter should become a separate reusable package such as `ccrs-react-python` or `ccrs-langgraph`.

## Surprises & Discoveries

- Observation: The previous plan text said JPype verification was still pending, but the current adapter has already completed a Java-backed scan.
  Evidence: Running `S:\anaconda\agent\python.exe -c "from react_agent.ccrs import CcrsRuntime; ... evaluate_turtle(...)"` returned a Python dictionary with `type='signifier'`, `pattern_id='https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green'`, and `utility=0.7`.

- Observation: Opportunistic CCRS annotations should not be wiped after every opportunistic node run.
  Evidence: `react_agent/nodes/llm_node_ccrs_v2.py` computes the latest tool call IDs from the newest `AIMessage` and filters `state.get("ccrs", [])` by `entry.get("tool_call_id")`. This lets the state retain audit/history while surfacing only the relevant CCRS entries to the prompt.

- Observation: The old broad classpath scan made the first Java-backed evaluation slow and fragile.
  Evidence: Earlier `resolve_classpath()` found 1245 jar entries and a real `evaluate_turtle(...)` call timed out after 30 seconds. The current declared dependency resolver returns 40 entries and the same scan completed in about one second.

- Observation: The active Python environment for this project is not the default `python.exe`.
  Evidence: `C:\Python313\python.exe` did not have `langchain_core`, while `S:\anaconda\agent\python.exe` imported `langchain_core`, `jpype`, and `rdflib` successfully.

- Observation: The current Git status shows `CCRS_README.md` deleted and `PLAN_CCRS_README.md` untracked.
  Evidence: `git status --short` reports `D CCRS_README.md` and `?? PLAN_CCRS_README.md`. Treat this as an in-progress documentation restructuring unless the user says to restore the old file.

- Observation: `http_post` responses in the maze run are not necessarily Turtle observations.
  Evidence: `logs/react_opportunistic_1_20260527_163125.log` shows `http_post` tool messages with content lengths 44 and 46 raising `rdflib.plugins.parsers.notation3.BadSyntax` when opportunistic CCRS tried to parse them as Turtle. This should be a skipped non-RDF observation, not an adapter failure.

## Decision Log

- Decision: Use JPype with an in-process JVM for normal Python-to-Java CCRS integration.
  Rationale: Opportunistic CCRS and future contingency CCRS need retained Java objects, runtime vocabulary discovery, and low per-cycle overhead. A sidecar HTTP process or one-shot CLI would add avoidable runtime boundaries and startup cost.
  Date/Author: 2026-05-14 / Codex and user direction

- Decision: Keep the baseline ReAct graph free of CCRS imports, CCRS state keys, and CCRS prompt variables.
  Rationale: CCRS should be an opt-in graph variant and adapter layer. The baseline graph remains the control path for experiments.
  Date/Author: 2026-05-14 / Codex

- Decision: Keep opportunistic CCRS advisory-only for now.
  Rationale: The current prompt injects JSON CCRS annotations as additional system context. It does not force or override the next tool call. Control-policy changes belong to a later contingency CCRS milestone.
  Date/Author: 2026-05-26 / User direction

- Decision: Keep `ccrs` state append-only.
  Rationale: Append-only state preserves audit/history and avoids losing annotations before downstream analysis. Current prompt injection already filters by the latest tool call IDs.
  Date/Author: 2026-05-27 / User correction and Codex implementation

- Decision: Replace `number_of_cycles` and `cycle_timings` with one `cycle` object.
  Rationale: The user wants the state to store only a cycle increment and current timestamp; experiment scripts can derive durations later. Compatibility wrappers should not be kept.
  Date/Author: 2026-05-27 / User correction and Codex implementation

- Decision: Use key-value audit events as the primary verification surface for normal opportunistic CCRS lifecycle events.
  Rationale: Stable event names and fields are easier for experiment scripts to parse than prose logs. Human-readable React CCRS logs remain useful for diagnostics and exceptions.
  Date/Author: 2026-05-26 / Codex

- Decision: Prefix React adapter CCRS audit events with `[REACT-CCRS-EVENT]` and event names under `react.ccrs...`.
  Rationale: Java CCRS library events use `[CCRS-EVENT]` and `ccrs...` event names. React-side events need a separate prefix so experiment logs can distinguish adapter behavior from reusable library behavior.
  Date/Author: 2026-05-27 / User direction and Codex implementation

- Decision: Use `react_agent/ccrs/README.md` as the React-specific CCRS adapter documentation file, and use `PLAN_CCRS_README.md` as the long-running executable plan.
  Rationale: The old root `CCRS_README.md` is no longer the right target for React adapter documentation. Keeping package documentation near the adapter and implementation state in this plan makes future sessions easier to resume.
  Date/Author: 2026-05-27 / User direction and Codex implementation

## Outcomes & Retrospective

The opportunistic CCRS adapter is no longer just a design direction. It has a runnable LangGraph node, lazy public imports through `react_agent.ccrs`, Java-backed `VocabularyMatcher.scanAll(...)` evaluation, append-only CCRS state, prompt-time filtering by latest tool call ID, and React-specific audit events for verification. The main remaining gap is testability: the adapter has been smoke-tested manually with the project Anaconda interpreter, but the repository does not yet contain focused tests or scripts that future sessions can run to prove the behavior without a full maze and LLM run. Documentation now points from the root README to the React-specific adapter documentation in `react_agent/ccrs/README.md`, while this file remains the long-running execution plan.

## Context and Orientation

This repository is `ccrs-react`, a Python ReAct/LangGraph agent that can run either a baseline graph or an opportunistic CCRS graph. ReAct means the agent alternates between LLM decisions and tool calls. LangGraph is the state-machine library that wires nodes such as `llm`, `tools`, and `opportunistic_ccrs`.

The React-specific CCRS documentation lives in [react_agent/ccrs/README.md](react_agent/ccrs/README.md). For broader CCRS concepts, start with [CCRS_LIBRARY.md](../ccrs-bdi/CCRS_LIBRARY.md); although that file focuses on BDI agents and the JaCaMo adapter, it explains the generic CCRS intention and points to further resources. The most directly relevant Java concept documents are the opportunistic CCRS [README.md](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/opportunistic/README.md) and contingency CCRS [README.md](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/README.md).

CCRS means Course Check and Revision Strategies. In this project there are two intended CCRS modes. Opportunistic CCRS reads RDF observations and produces advisory annotations such as a useful signifier or marker. Contingency CCRS will later evaluate failures, stuck states, uncertainty, retry, backtracking, and social consultation. This plan covers opportunistic CCRS stabilization first.

The reusable Java CCRS code lives in the sibling repository `../ccrs-bdi`. The Java module that matters for this first milestone is `../ccrs-bdi/ccrs-core`. It publishes Maven-local artifacts with coordinates `io.github.stefanmhsg.ccrs:ccrs-core:0.1.0-SNAPSHOT`. The Python runtime expects those artifacts in local Maven and resolves Java dependencies from local Maven or the Gradle cache.

The baseline graph is `react_agent/graph/graph.py`. It uses `react_agent/state/state.py`, `react_agent/nodes/llm_node.py`, and the plain `react_prompt` in `react_agent/prompts/react_prompt.py`. The CCRS graph is `react_agent/graph/graph_opportunistic_ccrs.py`. It uses `react_agent/ccrs/state.py`, `react_agent/nodes/llm_node_ccrs_v2.py`, `react_agent/nodes/tool_node.py`, and `react_agent/ccrs/opportunistic.py`.

The current CCRS graph shape is:

    llm -> tools -> opportunistic_ccrs -> llm

The `llm` node makes an LLM decision and increments state field `cycle` after the LLM call returns. The `tools` node executes the requested tools. The `opportunistic_ccrs` node inspects the latest `ToolMessage`, parses Turtle RDF with `rdflib`, converts triples to Java `RdfTriple` objects through JPype, calls Java `VocabularyMatcher.scanAll(...)`, and returns Python CCRS annotation dictionaries. LangGraph appends those dictionaries into the `ccrs` state channel because `react_agent/ccrs/state.py` annotates `ccrs` with `operator.add`.

The `cycle` state field is a dictionary:

    {"number": 1, "timestamp": "2026-05-27T13:33:12.123+00:00"}

It is not a timing object. Experiment scripts can derive elapsed time by comparing state snapshots or logs.

The current public adapter imports are exposed by `react_agent/ccrs/__init__.py`. Application code can import `opportunistic_ccrs_node`, `make_opportunistic_ccrs_node`, `CcrsRuntime`, `CcrsRuntimeError`, `get_default_runtime`, and `CcrsAgentState`.

## Milestones

Milestone 1 is to keep opportunistic CCRS runtime-solid and auditable. At the end of this milestone, a developer can run a small Java-backed scan with `S:\anaconda\agent\python.exe`, see a CCRS annotation dictionary returned, and see `[REACT-CCRS-EVENT]` logs showing adapter classpath resolution, JVM start, runtime readiness, evaluation, and detection.

Milestone 2 is to make the state and prompt path testable without live OpenAI calls. At the end of this milestone, a focused test or script should prove that `opportunistic_ccrs_node` appends only non-empty Java-backed results, that no-result paths return no state update, and that `llm_node_ccrs_v2.py` filters append-only CCRS history by latest tool call IDs.

Milestone 3 is to document and settle the adapter boundary. At the end of this milestone, root documentation links should point to the React CCRS adapter README, this plan should be discoverable, and repository guidance should prevent accidental scope expansion during CCRS work.

Milestone 4 is to prepare for contingency CCRS without implementing it prematurely. At the end of this milestone, the plan should describe the required Python state additions for RDF memory, current resource, tool interaction history, and failure situations, and should identify which Java contingency APIs will be wrapped first.

## Plan of Work

First, preserve the current opportunistic CCRS implementation and avoid broad rewrites. Keep `react_agent/ccrs/runtime.py` as the owner of JPype startup, Java classpath resolution, Java object creation, and Java result conversion. Keep `react_agent/ccrs/rdf_adapter.py` as the only Turtle-to-Python-triple parser. Keep `react_agent/ccrs/opportunistic.py` as the LangGraph node factory. Keep `react_agent/ccrs/state.py` as the CCRS graph state helper rather than moving the whole application state into the adapter package.

Second, add focused validation around the adapter boundary. This should be approached as a narrow adapter test, not as an end-to-end maze or LLM run. A minimal script or test should construct a `ToolMessage` with Turtle containing the default green signifier predicate `https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green`, pass it through `make_opportunistic_ccrs_node()`, and assert that the returned update contains one `ccrs` entry with `type == "signifier"`, a `pattern_id` ending in `#green`, the original `tool_call_id`, and `utility == 0.7`. Another test should use valid Turtle with no matching CCRS pattern and assert that the node returns `{}` rather than mutating `ccrs`. A third check should exercise the LangGraph reducer behavior by merging two returned `ccrs` updates and confirming that the list appends rather than replaces earlier annotations.

Third, improve prompt-path validation without calling the LLM. Extract the filtering logic from `react_agent/nodes/llm_node_ccrs_v2.py` into a small helper if that makes tests practical. The helper should accept messages and `ccrs` history, find latest tool call IDs from the most recent `AIMessage`, and return JSON text. It should return `"[]"` when nothing matches and JSON for only current tool-call-related entries when matches exist. This proves the append-only state design remains prompt-safe.

Fourth, maintain the documentation boundary. `react_agent/ccrs/README.md` is the React CCRS adapter documentation file and should be referenced by the root README and this plan. `PLAN_CCRS_README.md` is the execution plan and should record progress, decisions, discoveries, validation, and future work. `AGENTS.md` should remain concise and should direct future sessions to this plan before complex CCRS work.

Fifth, preserve RDF memory across graph cycles as future work. The intention is to retain machine-readable observations across cycles so later CCRS logic can reason over what the agent has learned, not just the latest prompt text. This is especially relevant for contingency behavior, where recovery may depend on the current resource, prior RDF observations, repeated failures, or a changed interpretation of earlier observations.

Sixth, capture structured HTTP request, response, and failure history from Python tools as future work. The intention is to make tool interaction history auditable and machine-readable: method, URL, status, headers or content type, selected body details, exception type, timestamp, tool name, tool call ID, and cycle. This history gives contingency CCRS a concrete failure surface instead of forcing it to infer failures from free-form tool text.

Seventh, add contingency CCRS evaluation for tool failures only after opportunistic CCRS is test-covered. The first contingency step should map structured tool failures into the Java contingency model, evaluate candidate revision strategies, and return advisory annotations through a separate state/prompt path. Do not mix contingency behavior into the opportunistic CCRS node.

## Concrete Steps

Run all commands from repository root `S:\dev\ma\ccrs-react`.

Use the project interpreter, not the default Windows Python:

    S:\anaconda\agent\python.exe -c "import sys; print(sys.executable)"

Expected output begins with:

    S:\anaconda\agent\python.exe

Compile the Python package after changes:

    S:\anaconda\agent\python.exe -m compileall react_agent

Expected output lists `react_agent` subdirectories and exits with code 0.

Confirm both graph modules still build:

    S:\anaconda\agent\python.exe -c "from react_agent.graph.graph import build_graph as b1; from react_agent.graph.graph_opportunistic_ccrs import build_graph as b2; print(type(b1()).__name__); print(type(b2()).__name__)"

Expected output is:

    CompiledStateGraph
    CompiledStateGraph

Confirm Java-backed opportunistic CCRS still scans through JPype:

    S:\anaconda\agent\python.exe -c "from react_agent.ccrs import CcrsRuntime; rt=CcrsRuntime.from_maven_local(); data='@prefix maze: <https://kaefer3000.github.io/2021-02-dagstuhl/vocab#> .\n<http://example.org/cell> maze:green <http://example.org/target> .'; print(rt.evaluate_turtle(data, context={'tool_call_id':'smoke','tool_name':'http_get','agent_name':'SmokeAgent','cycle':'1'}))"

Expected output includes a dictionary with:

    'type': 'signifier'
    'target': 'http://example.org/target'
    'pattern_id': 'https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green'
    'utility': 0.7
    'tool_call_id': 'smoke'

Check for stale state names before finalizing state-related edits:

    rg -n "number_of_cycles|cycle_timings|scan_turtle|scan_triples|Deprecated compatibility" react_agent README.md

Expected output is empty.

## Validation and Acceptance

The opportunistic CCRS adapter is acceptable when all of the following are true. The package compiles with `S:\anaconda\agent\python.exe -m compileall react_agent`. Both graph builders return `CompiledStateGraph`. A Java-backed Turtle scan returns at least one opportunistic CCRS dictionary for the default green signifier pattern. The scan path emits `[REACT-CCRS-EVENT]` lines for adapter classpath/runtime/evaluation/detection when logging is enabled. Non-RDF tool output emits `react.ccrs.opportunistic.skipped reason=invalid_turtle` instead of an error stack trace. The `ccrs` state channel remains append-only, and the prompt path filters by latest tool call IDs rather than clearing state. No deprecated runtime aliases named `scan_turtle` or `scan_triples` remain.

Full maze success is not required for opportunistic adapter acceptance because it depends on the external maze server and live LLM calls. A later experiment validation can run `python main.py --graph-name graph_opportunistic_ccrs --agent-name "CCRSAgent" --log-level "DEBUG"` once the maze server and OpenAI credentials are available.

## Idempotence and Recovery

The local Maven publishing step in `../ccrs-bdi` is safe to rerun when Java CCRS artifacts change:

    ./gradlew publishToMavenLocal

If the Gradle wrapper needs to download Gradle, it may require network approval in Codex. After publishing, rerun the Java-backed scan command from this plan.

The JPype JVM cannot be restarted inside the same Python process after shutdown, so validation commands should use separate short Python processes. If a JPype classpath mistake occurs, fix `react_agent/ccrs/runtime.py` and rerun the command in a new process.

Do not revert user-side documentation restructuring unless explicitly asked. In particular, if `CCRS_README.md` is deleted and `PLAN_CCRS_README.md` is untracked, treat that as active user work and update links deliberately.

## Artifacts and Notes

Known successful smoke evidence from prior work:

    Classpath entries before narrowing: 1245
    Classpath entries after narrowing: 40
    Java-backed result: [{'ccrs_type': 'opportunistic', 'type': 'signifier', 'target': 'http://example.org/target', 'pattern_id': 'https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green', 'utility': 0.7, ...}]

Important log events to preserve:

    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.classpath.resolved entries=40 ...
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.jvm.start classpath_entries=40
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.runtime.ready scanner=ccrs.core.opportunistic.VocabularyMatcher
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.evaluate ...
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.detected ...
    [REACT-CCRS-EVENT] event=react.ccrs.opportunistic.cycle_annotations ...

Current documentation boundary:

    react_agent/ccrs/README.md is the React CCRS adapter documentation file.
    PLAN_CCRS_README.md is the long-running executable plan.
    AGENTS.md records repository guidance for future Codex sessions.

## Interfaces and Dependencies

The Python interpreter for validation is `S:\anaconda\agent\python.exe`. The default `C:\Python313\python.exe` may not have the required LangChain dependencies.

The core public Python adapter interface lives in `react_agent/ccrs/__init__.py` and should continue to expose:

    CcrsAgentState
    CcrsRuntime
    CcrsRuntimeError
    get_default_runtime
    make_opportunistic_ccrs_node
    opportunistic_ccrs_node

`CcrsRuntime` in `react_agent/ccrs/runtime.py` should continue to provide:

    CcrsRuntime.from_maven_local(...)
    CcrsRuntime.evaluate_turtle(content, context=None)
    CcrsRuntime.evaluate_triples(triples, context=None)
    CcrsRuntime.resolve_classpath()

Deprecated compatibility aliases such as `scan_turtle` and `scan_triples` should not be reintroduced.

`CcrsAgentState` in `react_agent/ccrs/state.py` should continue to include:

    messages: Annotated[Sequence[BaseMessage], add_messages]
    cycle: dict[str, Any]
    ccrs: Annotated[list[dict[str, Any]], add]

The `cycle` object has `number` and UTC `timestamp`. The `ccrs` list contains dictionaries converted from Java `OpportunisticResult` values. Each opportunistic CCRS dictionary should include `ccrs_type`, `type`, `target`, `pattern_id`, `utility`, `metadata`, and `tool_call_id` when the source tool message has an ID.

The Java dependency is the Maven-local artifact `io.github.stefanmhsg.ccrs:ccrs-core:0.1.0-SNAPSHOT`, plus declared Jena 5.6.0 runtime dependencies resolved by `react_agent/ccrs/runtime.py`.

## Revision Notes

2026-05-27: Converted this file from a stale architecture/progress note into a formal ExecPlan. The revision preserves the CCRS adapter direction, updates implementation status for JPype, append-only CCRS state, `cycle` state, and key-value audit logging, and records remaining work as executable milestones with validation commands.

2026-05-27: Updated documentation ownership after user direction. `react_agent/ccrs/README.md` is now the React-specific CCRS adapter documentation file, root `README.md` links there, and `AGENTS.md` records scope-control and CCRS-context guidance for future sessions.

2026-05-27: Updated React adapter log naming after user direction. Python adapter logs now use `[React CCRS][Opportunistic]`, and adapter audit events use `[REACT-CCRS-EVENT] event=react.ccrs...` so they can be separated from Java CCRS library events.

2026-05-27: Updated invalid RDF handling after log analysis. Non-Turtle tool outputs are now skipped with `reason=invalid_turtle` instead of being logged as opportunistic CCRS evaluation failures.
