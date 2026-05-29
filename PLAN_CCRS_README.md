# PLAN_CCRS_README: Stabilize the CCRS ReAct Adapter Plan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

No repository-local `PLANS.md` or `.agent/PLANS.md` guide is currently checked in. This document follows the local `PLAN_<SCOPE>.md` convention and is intended to be self-contained enough for a future Codex session to resume CCRS adapter work without prior chat history.

## Purpose / Big Picture

The goal is to make the Python ReAct/LangGraph agent consume the reusable Java Course Check and Revision Strategy libraries through a small adapter layer. After this work, a user should be able to run the `graph_opportunistic_ccrs` graph, observe Java-backed opportunistic CCRS annotations in the LangGraph state, and verify the React adapter path through stable `[REACT-CCRS-EVENT]` audit log lines. The first deliverable was opportunistic CCRS: RDF observations from tool messages are interpreted by Java `ccrs-core` and injected as advisory context into the next LLM decision. The current contingency work starts with the adapter boundary for failures, stuck states, retry, backtracking, and stop behavior; graph activation and prompt/control integration remain future work.

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
- [x] (2026-05-27) Added a React adapter Java logging bridge that writes Java `ccrs-core` JUL records to a per-run `logs/<run>.java.log` companion file.
- [x] (2026-05-27) Updated root documentation links so `README.md` points to the React CCRS adapter documentation in `react_agent/ccrs/README.md` and this plan.
- [x] (2026-05-27) Established `react_agent/ccrs/README.md` as the React-specific CCRS documentation file while this file remains the executable implementation plan.
- [x] (2026-05-27) Added concise repository guidance in `AGENTS.md` for scope approval, plan usage, Decision Log highlighting, and CCRS conceptual starting points.
- [x] (2026-05-27) Verified milestones 1-3 with smoke checks for compile/build, simple and structural Java-backed opportunistic scans, invalid-Turtle skipping, React/Java log output, and JaCaMo opportunistic adapter feature comparison.
- [x] (2026-05-29) Split `react_agent/ccrs` into an import-compatible opportunistic subpackage and a new contingency subpackage.
- [x] (2026-05-29) Implemented Package A through a Java contingency boundary that maps Python `Situation` values to Java `Situation`, supplies a Java `CcrsContext` proxy, calls `ContingencyCcrs.evaluateWithTrace(...)`, records traces, and converts suggestions/no-help/evaluations back to Python dictionaries.
- [x] (2026-05-29) Aligned contingency adapter class and file names with Java CCRS Maven library names where Python naming allows it.
- [x] (2026-05-29) Split shared Java runtime mechanics from approach-specific wrappers: `java_runtime.py` owns JPype/classpath/logging, `opportunistic/vocabulary_matcher.py` owns Java `VocabularyMatcher`, and `contingency/contingency_ccrs.py` owns Java `ContingencyCcrs`.
- [x] (2026-05-29) Implemented the first Package B boundary: `InMemoryCcrsContext.from_messages(...)` derives RDF query triples and Java `Interaction` records from normal LangGraph `AIMessage`/`ToolMessage` history, considering every parseable Turtle tool message.
- [x] (2026-05-29) Split Java `Interaction` derivation into `react_agent/ccrs/contingency/interaction.py`, with a generic default outcome classifier and a pluggable classifier hook for scenario-specific policies such as MaSE RDF error interpretation.
- [x] (2026-05-29) Aligned React `InMemoryCcrsTraceHistory` method names with the Java `CcrsContext` trace-history contract.
- [x] (2026-05-29) Implemented LangChain4j capability reuse through Java `ServiceLoader`: `ContingencyCcrs.from_maven_local(modules=("ccrs-core", "ccrs-langchain4j"), discover_strategy_providers=True)` registers Java `Langchain4jPredictionStrategyProvider` and the `prediction_llm` strategy when an API key is configured.
- [x] (2026-05-29) Implemented A2A capability reuse through Java `ServiceLoader`: `ContingencyCcrs.from_maven_local(modules=("ccrs-core", "ccrs-a2a"), discover_strategy_providers=True)` registers Java `A2aConsultationStrategyProvider` and the `consultation` strategy when local A2A jars are available.
- [ ] Continue contingency CCRS adapter design discussion; current working notes are recorded in the `Contingency CCRS Design Discussion` section.
- [ ] Design and implement contingency CCRS evaluation for explicit tool errors and semantic escalation cases after the adapter boundary is settled.
- [ ] Ensure the same `InMemoryCcrsTraceHistory` instance survives across contingency CCRS cycles when graph routing is implemented.
- [ ] Decide whether and when the adapter should become a separate reusable package such as `ccrs-react-python` or `ccrs-langgraph`.

## Surprises & Discoveries

- Observation: The previous plan text said JPype verification was still pending, but the current adapter has already completed a Java-backed scan.
  Evidence: Running `S:\anaconda\agent\python.exe -c "from react_agent.ccrs.opportunistic.vocabulary_matcher import VocabularyMatcher; ... evaluate_turtle(...)"` returned a Python dictionary with `type='signifier'`, `pattern_id='https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green'`, and `utility=0.7`.

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

- Observation: Java CCRS logs were not missing because Java failed to log; they were missing from the Python file because Java JUL handlers and Python file handlers are separate logging systems.
  Evidence: `ccrs-core` uses `java.util.logging.Logger` in classes such as `CcrsVocabularyLoader`, `CcrsVocabulary`, and `VocabularyMatcher`, while `react_agent/utils/logging_config.py` writes only Python logging records to `logs/<run>.log`.

- Observation: The JaCaMo opportunistic adapter has Jason-specific integration points that should not be copied directly into the React adapter.
  Evidence: `ccrs-jacamo` provides BRF/belief-base integration through `CcrsAgent`, CArtAgO percept batching through `CcrsAgentArch`, and deterministic AgentSpeak option reordering through `ccrs.jacamo.jason.opportunistic.prioritize`. The React adapter covers the shared CCRS library boundary by calling Java `VocabularyMatcher.scanAll(...)`, but intentionally exposes results as advisory prompt context rather than Jason `ccrs/3` beliefs or forced option ordering.

- Observation: MaSE already supports RDF error bodies when the client explicitly asks for an RDF media type.
  Evidence: [ErrorResponseBuilder.java](../mase/mase-server/src/main/java/org/maze/api/ErrorResponseBuilder.java) serializes `mase:errorMessage`, `mase:errorStatusCode`, and `http:statusCodeValue` triples for `text/turtle`, JSON-LD, RDF/XML, or N-Triples `Accept` headers. [ErrorResponseBuilderTest.java](../mase/mase-server/src/test/java/org/maze/api/ErrorResponseBuilderTest.java) verifies Turtle and JSON-LD error bodies and verifies that wildcard or JSON-only requests keep the legacy non-RDF fallback.

- Observation: React tools previously prevented MaSE RDF errors from reaching CCRS.
  Evidence: [get.py](react_agent/tools/get.py) and [post.py](react_agent/tools/post.py) used `requests.raise_for_status()`, so HTTP 4xx/5xx response bodies were replaced with Python error dictionaries. They now send `Accept: text/turtle, text/plain;q=0.1` by default and return the raw HTTP body for any HTTP response. Actual tool invocation errors, such as unknown tools or request exceptions, are still represented as normal `ToolMessage` errors by [tool_node.py](react_agent/nodes/tool_node.py).

- Observation: Java `CcrsContext.query(...)` is not the only context path used by contingency strategies.
  Evidence: [CcrsContext.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/rdf/CcrsContext.java) defines `query(...)` as RDF pattern matching and its default `getMemoryTriples(...)` and `getNeighborhood(...)` methods delegate to it. [ConsultationStrategy.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/strategies/social/ConsultationStrategy.java) calls `query(...)` directly for A2A agent-card metadata and also uses `getNeighborhood(...)`. [PredictionLlmStrategy.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/strategies/internal/prediction/PredictionLlmStrategy.java) uses `getNeighborhood(...)`, so it reaches `query(...)` indirectly. [BacktrackStrategy.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/strategies/internal/BacktrackStrategy.java) instead relies mainly on `getRecentInteractions(...)` and each interaction's perceived RDF state. [RetryStrategy.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/strategies/internal/RetryStrategy.java) and [StopStrategy.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/strategies/internal/StopStrategy.java) depend on CCRS trace history rather than RDF query.

- Observation: Java contingency capabilities are strategy registrations, not `CcrsContext` fields.
  Evidence: [LlmClient.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/LlmClient.java) is the provider-neutral completion interface used by [PredictionLlmStrategy.java](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/strategies/internal/prediction/PredictionLlmStrategy.java). Optional Java modules such as [Langchain4jPredictionStrategyProvider.java](../ccrs-bdi/ccrs-langchain4j/src/main/java/ccrs/capabilities/llm/langchain4j/Langchain4jPredictionStrategyProvider.java) register strategies through Java `ServiceLoader`.

- Observation: The Java LangChain4j capability can be reused directly from React when its module and SDK jars are on the JPype classpath.
  Evidence: [ccrs-langchain4j README.md](../ccrs-bdi/ccrs-langchain4j/README.md) defines the module as an optional `ServiceLoader` capability. A local smoke with `modules=("ccrs-core", "ccrs-langchain4j")`, provider discovery enabled, and a configured `OPENAI_API_KEY` registered strategies `retry`, `backtrack`, `stop`, and `prediction_llm` through [Langchain4jPredictionStrategyProvider.java](../ccrs-bdi/ccrs-langchain4j/src/main/java/ccrs/capabilities/llm/langchain4j/Langchain4jPredictionStrategyProvider.java).

- Observation: The Java A2A capability can be reused directly from React when its module and SDK jars are on the JPype classpath.
  Evidence: [ccrs-a2a README.md](../ccrs-bdi/ccrs-a2a/README.md) defines the module as an optional `ServiceLoader` capability. A local smoke with `modules=("ccrs-core", "ccrs-a2a")` and provider discovery enabled registered strategies `retry`, `backtrack`, `stop`, and `consultation` through [A2aConsultationStrategyProvider.java](../ccrs-bdi/ccrs-a2a/src/main/java/ccrs/capabilities/a2a/A2aConsultationStrategyProvider.java).

- Observation: Provider discovery must use JPype's classloader after the JVM has already started.
  Evidence: A lifecycle smoke that first created a core-only `ContingencyCcrs` and then created an A2A-enabled wrapper did not discover `consultation` through the default thread context classloader. Passing `org.jpype.JPypeContext.getInstance().getClassLoader()` to `ContingencyCcrsFactory.withDefaultsAndDiscoveredProviders(...)` made the same lifecycle discover and register `consultation`.

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

- Decision: Capture Java CCRS library logs in a per-run companion file named `logs/<run>.java.log`.
  Rationale: The Java library uses `java.util.logging`, while the React agent uses Python logging. Writing both runtimes into one file risks handler conflicts and interleaving, especially on Windows. A companion file keeps Java library logs auditable and tied to the same run name without coupling Java logging to Python internals.
  Date/Author: 2026-05-27 / User direction and Codex implementation

- Decision: Contingency CCRS should operate on the normal LangGraph `messages` state rather than a separate structured HTTP/tool history channel.
  Rationale: The message state already preserves the clear cause-effect trace the agent used, including tool calls, tool responses, and error responses. Adding a separate structured tool-history state would duplicate that trace and is not desired for the current React adapter direction.
  Date/Author: 2026-05-27 / User direction

- Decision: Keep the React CCRS adapter generic by preferring standard LangGraph/ReAct messages over custom duplicated state fields.
  Rationale: The adapter should be shaped like a typical reusable React/LangGraph integration. `messages` remains the source of truth for observations, tool calls, tool responses, and errors. Extra state should be limited to adapter outputs that cannot be represented as normal messages, such as advisory CCRS annotations.
  Date/Author: 2026-05-27 / User direction

- Decision: Package B query scope is every parseable `ToolMessage`.
  Rationale: React contingency context should not restrict RDF lookup to successful `GET` observations. MaSE can encode error responses as RDF, and contingency strategies benefit from querying both successful observations and parseable error bodies from the normal message history.
  Date/Author: 2026-05-29 / User direction and Codex implementation

- Decision: Reuse the Java LangChain4j capability for contingency LLM prediction instead of maintaining a React-side `LlmClient` proxy.
  Rationale: Contingency `PredictionLlmStrategy` should use the stronger Java-configured model, currently LangChain4j's default `gpt-5.5`, rather than the fast React loop model. Reusing `ccrs-langchain4j` keeps Package E aligned with the JaCaMo capability model and avoids duplicate Python LLM adapter code.
  Date/Author: 2026-05-29 / User direction and Codex implementation

- Decision: Reuse the Java A2A capability as provided instead of implementing an A2A consultation channel in Python.
  Rationale: `ccrs-a2a` already isolates the A2A SDK dependency and contributes `A2aConsultationStrategyProvider` through Java `ServiceLoader`. React should make that provider visible on the JPype classpath and let Java register `ConsultationStrategy`, preserving the same capability boundary as JaCaMo.
  Date/Author: 2026-05-29 / User direction and Codex implementation

## Outcomes & Retrospective

The opportunistic CCRS adapter is no longer just a design direction. It has a runnable LangGraph node, direct concrete module imports, Java-backed `VocabularyMatcher.scanAll(...)` evaluation, append-only CCRS state, prompt-time filtering by latest tool call ID, React-specific audit events, and Java companion logs for verification. Package A for contingency CCRS now has a Python-to-Java boundary that can evaluate a Java `Situation` and return a Python trace dictionary, but it is not connected to graph routing yet. Current validation is smoke-oriented: compile the package, build both graphs, run Java-backed opportunistic and contingency scans with the project Anaconda interpreter, and inspect the React and Java log outputs. Documentation now points from the root README to the React-specific adapter documentation in `react_agent/ccrs/README.md`, while this file remains the long-running execution plan.

## Context and Orientation

This repository is `ccrs-react`, a Python ReAct/LangGraph agent that can run either a baseline graph or an opportunistic CCRS graph. ReAct means the agent alternates between LLM decisions and tool calls. LangGraph is the state-machine library that wires nodes such as `llm`, `tools`, and `opportunistic_ccrs`.

The React-specific CCRS documentation lives in [react_agent/ccrs/README.md](react_agent/ccrs/README.md). For broader CCRS concepts, start with [CCRS_LIBRARY.md](../ccrs-bdi/CCRS_LIBRARY.md); although that file focuses on BDI agents and the JaCaMo adapter, it explains the generic CCRS intention and points to further resources. The most directly relevant Java concept documents are the opportunistic CCRS [README.md](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/opportunistic/README.md) and contingency CCRS [README.md](../ccrs-bdi/ccrs-core/src/main/java/ccrs/core/contingency/README.md).

CCRS means Course Check and Revision Strategies. In this project there are two intended CCRS modes. Opportunistic CCRS reads RDF observations and produces advisory annotations such as a useful signifier or marker. Contingency CCRS will later evaluate failures, stuck states, uncertainty, retry, backtracking, and social consultation. This plan covers opportunistic CCRS stabilization first.

The reusable Java CCRS code lives in the sibling repository `../ccrs-bdi`. The Java module that matters for this first milestone is `../ccrs-bdi/ccrs-core`. It publishes Maven-local artifacts with coordinates `io.github.stefanmhsg.ccrs:ccrs-core:0.1.0-SNAPSHOT`. The Python runtime expects those artifacts in local Maven and resolves Java dependencies from local Maven or the Gradle cache.

The baseline graph is `react_agent/graph/graph.py`. It uses `react_agent/state/state.py`, `react_agent/nodes/llm_node.py`, and the plain `react_prompt` in `react_agent/prompts/react_prompt.py`. The CCRS graph is `react_agent/graph/graph_opportunistic_ccrs.py`. It uses `react_agent/ccrs/state.py`, `react_agent/nodes/llm_node_ccrs_v2.py`, `react_agent/nodes/tool_node.py`, and the opportunistic CCRS package in `react_agent/ccrs/opportunistic/`.

The current CCRS graph shape is:

    llm -> tools -> opportunistic_ccrs -> llm

The `llm` node makes an LLM decision and increments state field `cycle` after the LLM call returns. The `tools` node executes the requested tools. The `opportunistic_ccrs` node inspects the latest `ToolMessage`, parses Turtle RDF with `rdflib`, converts triples to Java `RdfTriple` objects through JPype, calls Java `VocabularyMatcher.scanAll(...)`, and returns Python CCRS annotation dictionaries. LangGraph appends those dictionaries into the `ccrs` state channel because `react_agent/ccrs/state.py` annotates `ccrs` with `operator.add`.

The `cycle` state field is a dictionary:

    {"number": 1, "timestamp": "2026-05-27T13:33:12.123+00:00"}

It is not a timing object. Experiment scripts can derive elapsed time by comparing state snapshots or logs.

The adapter should use concrete module imports rather than root-package compatibility exports. Application code imports opportunistic graph nodes from `react_agent.ccrs.opportunistic.opportunistic`, Java runtime mechanics from `react_agent.ccrs.java_runtime`, CCRS graph state from `react_agent.ccrs.state`, Java `VocabularyMatcher` from `react_agent.ccrs.opportunistic.vocabulary_matcher`, and contingency Package A objects from `react_agent.ccrs.contingency`.

## Milestones

Milestone 1 is complete. Its purpose was to keep opportunistic CCRS runtime-solid and auditable. A developer can run small Java-backed scans with `S:\anaconda\agent\python.exe`, see CCRS annotation dictionaries returned, and see `[REACT-CCRS-EVENT]` logs showing adapter classpath resolution, JVM start, runtime readiness, evaluation, and detection.

Milestone 2 is complete. Its purpose was to keep the adapter boundary smoke-verifiable without live OpenAI calls. The commands in this plan demonstrate that Java-backed scans produce annotations, invalid Turtle is skipped without stack traces, graph builders still compile, and prompt injection continues to filter append-only CCRS history by latest tool call IDs.

Milestone 3 is complete. Its purpose was to document and settle the adapter boundary. Root documentation links point to the React CCRS adapter README, this plan is discoverable, and repository guidance prevents accidental scope expansion during CCRS work.

Milestone 4 is to implement contingency CCRS incrementally without wiring graph control prematurely. Package A now wraps the Java contingency API. The remaining milestone work is to describe and implement how contingency evaluation reads the existing LangGraph `messages` state to derive contingency situations, current resource context, interaction history, RDF query context, strategy-selection behavior, and graph-routing decisions.

## Contingency CCRS Design Discussion

This section records the current design status for the React contingency CCRS adapter. Package status markers mean:

- `(Complete)`: the adapter boundary described here exists and has been smoke-validated.
- `(In-Progress)`: part of the boundary exists, but important graph/runtime integration remains.
- `(Open)`: design direction exists, but implementation has not started.

The emerging packages are:

### Package A: Java Contingency Bridge (Complete)

This package owns the Python-to-Java boundary for contingency CCRS. It maps React/Python values to Java `Situation`, provides calls into `ContingencyCcrs.evaluate(...)`, and converts Java `StrategyResult.Suggestion` and `StrategyResult.NoHelp` values into Python dictionaries suitable for LangGraph state and logs.

At a general CCRS level, contingency CCRS should be treated as a strategy-evaluation layer, not as another vocabulary scanner. The Java input is currently a `Situation` with fields such as type, trigger, current resource, target resource, failed action, error information, and metadata. The current Java enum values `FAILURE`, `STUCK`, `UNCERTAINTY`, and `PROACTIVE` should be treated with care. This situation typing is one of the least developed parts of the current model, and it is not yet clear that an enum is the ideal long-term representation for contingency triggers.

This package also needs to expose strategy-selection behavior instead of hiding it. The core does not always mean "evaluate the first applicable strategy and stop." `ContingencyConfiguration` supports `SEQUENTIAL`, `BEST_PER_LEVEL`, and `PARALLEL`, and the default currently uses trace-based strategy selection. Depending on configuration and learned trace history, multiple strategies can be evaluated and selected suggestions are ranked by confidence. `StopStrategy` is treated specially as a fallback and is skipped when recovery suggestions already exist. React contingency design should log the strategy-selection policy, evaluated strategies, selected suggestions, Java trace identifiers, and no-help results rather than assuming one strategy maps to one outcome.

The React equivalent of JaCaMo `ccrs.contingency.evaluate(...)` belongs here. It should build the Java `Situation`, provide the React `CcrsContext`, call `ContingencyCcrs.evaluate(...)`, convert results, and emit auditable React-side events.

Implementation status: Package A now exists under `react_agent/ccrs/contingency/`. The boundary uses `ContingencyCcrs.evaluate(...)` to normalize a Python `Situation`, create a Java `Situation`, pass a Java `CcrsContext` proxy, call `ContingencyCcrs.evaluateWithTrace(...)`, explicitly record the resulting Java trace on the Python context, and return a Python dictionary containing the trace id, strategy-selection fields, selected results, per-strategy evaluations, suggestions, no-help results, opportunistic guidance, top suggestion, and stop flag. This stops at the adapter boundary; no LangGraph node or decision-route integration has been added yet.

### Package B: React CcrsContext From Messages (Complete)

This package adapts normal LangGraph/ReAct `messages` into the Java `CcrsContext` contract. It should provide `CcrsContext.query(...)`, interaction history, current resource lookup, agent identity, and CCRS trace history without introducing duplicated HTTP-history or RDF-memory state unless a concrete boundary requires it.

The Java `CcrsContext.query(subject, predicate, object)` contract is RDF pattern matching. `null` means wildcard, and the result is a list of `RdfTriple` values matching the pattern. In React, `query(...)` should answer from all parseable Turtle `ToolMessage` bodies in normal message history, including RDF error bodies. Ordering is currently message order, and Java interaction history is returned most-recent first. Bounded windows can be added later if prompt size or evaluation cost becomes a concrete issue.

The adapter should stay message-driven for now. The normal LangGraph `messages` state already carries the cause-effect sequence of `AIMessage.tool_calls` and `ToolMessage` responses. Java `Interaction` records are derived from existing AI/tool message pairs by [interaction.py](react_agent/ccrs/contingency/interaction.py): method and URI come from tool-call arguments, outcome comes from a generic default classifier, perceived state comes from parseable Turtle tool bodies, and logical source is the request URI when available. The default classifier uses only generic LangGraph message fields: optional `ToolMessage.response_metadata["http_status"]`, `ToolMessage.status`, and existing JSON tool-error wrappers. HTTP API responses are not treated as tool invocation failures by default; they remain raw tool message content so `CcrsContext.query(...)` can parse their RDF without requiring adapter-specific metadata. Scenario-specific interpretation, such as classifying MaSE RDF error bodies as client/server failures, should be supplied through the optional outcome-classifier hook rather than hard-coded in [ccrs_context.py](react_agent/ccrs/contingency/ccrs_context.py). Current React messages do not store explicit request and response timestamps, so the first Package B boundary uses message positions as stable monotonic timestamps. That gives Java strategies deterministic recency ordering without inventing a separate timing state.

For the MaSE maze scenario, `currentResource` can reasonably mean the agent's current location. This is context-dependent, not universal adapter logic. The React adapter should preserve the generic parameter while documenting the agent-designer rationale for how it is derived. A likely maze interpretation is "last known successful location," but failed `GET` and `POST` attempts complicate that. If the agent tries several requests that all fail, the current resource probably remains the last successful location rather than the last attempted target. This should remain explicit policy, not hidden in generic CCRS code.

Trace history also belongs in this package. JaCaMo handles trace history through its adapter context rather than through the belief base. `JasonCcrsContext` owns an `InMemoryCcrsTraceHistory` and implements `getLastCcrsInvocation()`, `getCcrsHistory(maxCount)`, and `recordCcrsInvocation(trace)`. React now follows the same adapter-context pattern with [in_memory_ccrs_trace_history.py](react_agent/ccrs/contingency/in_memory_ccrs_trace_history.py), which uses the same method names and stores Java `CcrsTrace` objects for [ccrs_context.py](react_agent/ccrs/contingency/ccrs_context.py). This matters because retry limits, stop exhaustion, and trace-based strategy selection depend on recorded traces. The important remaining lifecycle requirement belongs to Package C: graph routing must reuse the same `InMemoryCcrsTraceHistory` instance across contingency CCRS cycles for an agent run. If each contingency call creates a fresh `InMemoryCcrsContext.from_messages(...)` without passing the existing trace history, Java strategies will see empty trace history every time, making retry attempts, stop exhaustion, and trace-based selection behave as if every contingency invocation were the first one.

### Package C: Escalation And Graph Routing (Open)

This package decides when contingency CCRS runs and how control moves through the graph. The target scope is broader than actual tool/runtime errors. Contingency CCRS should eventually handle semantic failure as well: low progress, repeated unproductive actions, blocked navigation, missing expected affordances, contradictory observations, or other cases where a request technically succeeds but the agent is no longer making useful progress. The open design problem is deciding when the React agent should escalate to contingency CCRS at all.

Agent designers need a way to specify escalation mode. Candidate inputs include non-successful API/tool responses, semantic progress metrics, repeated unproductive cycles, and an LLM-facing self-escalation hook. The adapter may also expose a tool that lets the LLM request contingency evaluation; the agent designer can choose whether to include that tool.

The decision node should import a small helper from the React CCRS adapter to route control. The current direction is that contingency CCRS should be authoritative while it is invoked. Opportunistic CCRS is advisory-only, but contingency evaluation should be able to skip normal tool execution when a contingency activation flag is set. One possible graph shape is `llm -> decision -> tools -> ccrs_node -> llm` in normal operation, with `decision -> ccrs_node` when contingency is active. Another variant evaluates an LLM-emitted tool call first and then invokes contingency CCRS based on the result. This variant should be explicit and auditable.

A small contingency activation state should record whether contingency CCRS is active for a given cycle, why it was activated, and which cycle it belongs to. This keeps experiment inspection straightforward: a run log or state snapshot should show exactly which cycles invoked contingency CCRS.

Stop behavior should be deterministic. If contingency CCRS returns a stop suggestion, the React graph should terminate automatically instead of forcing another tool call. This likely requires changing the current CCRS LLM path, because `llm_node_ccrs_v2.py` currently binds tools with `tool_choice="any"`.

### Package D: CCRS Node, State, Prompt, And Correlation (Open)

This package owns how opportunistic and contingency outputs are represented in LangGraph state and surfaced to the LLM. Consider evolving the current `opportunistic_ccrs_node` into a more general `ccrs_node` that owns both opportunistic and contingency CCRS processing. Opportunistic processing remains the default path after tool observations. Contingency processing is gated behind state set by the decision node or self-escalation tool.

The output state probably should split opportunistic and contingency annotations. Opportunistic CCRS produces preference annotations over RDF observations; contingency CCRS produces strategy suggestions and may also produce opportunistic guidance. A likely state shape is separate append-only channels for opportunistic CCRS annotations and contingency CCRS suggestions, with prompt injection rendering them in separate sections.

Prompt injection should treat contingency differently from opportunistic CCRS. Contingency suggestions should be surfaced with stronger and more directive wording than opportunistic advisory context, while still preserving a clean audit trail of what Java suggested.

Contingency strategies may output `OpportunisticResult` guidance. If a contingency strategy emits such guidance, for example `BacktrackStrategy` guidance for backtrack steps or unexplored options, that guidance should be added as normal opportunistic CCRS items rather than hidden inside the contingency suggestion only.

Correlation is a known open issue. Current opportunistic CCRS activates after the `tools` node, scans the latest `ToolMessage` when it is parseable Turtle, stores entries with the source `tool_call_id`, and prompt injection later filters entries by the most recent `AIMessage.tool_calls`. That works for tool-observation-derived annotations. It may not work for contingency-generated opportunistic guidance, because those entries are not naturally caused by a new tool call. React contingency design may need richer correlation, such as cycle, origin, target URI, source RDF triples, current resource, strategy id, or trace id. Triple-based surfacing is worth investigating because opportunistic CCRS notes target specific RDF triples or triple-derived targets. Surfaced guidance may also need a consumed/dispensed marker so relevant guidance can be shown once without becoming permanent prompt noise.

### Package E: Optional Capability Integrations (Complete)

Both optional Java-side capability paths are now available through Java `ServiceLoader`. The React adapter reuses the Java modules as provided instead of implementing Python equivalents.

For `PredictionLlmStrategy`, React reuses the Java LangChain4j capability module as provided. [java_runtime.py](react_agent/ccrs/java_runtime.py) resolves the `ccrs-langchain4j` runtime jars when the module is requested. [contingency_ccrs.py](react_agent/ccrs/contingency/contingency_ccrs.py) can create Java `ContingencyCcrs` through `ContingencyCcrsFactory.withDefaultsAndDiscoveredProviders()` when `discover_strategy_providers=True`. With `modules=("ccrs-core", "ccrs-langchain4j")`, Java `ServiceLoader` discovers [Langchain4jPredictionStrategyProvider.java](../ccrs-bdi/ccrs-langchain4j/src/main/java/ccrs/capabilities/llm/langchain4j/Langchain4jPredictionStrategyProvider.java), creates `Langchain4jLlmClient.fromEnvironment()`, and registers `PredictionLlmStrategy` when `OPENAI_API_KEY` or `LLM_API_KEY` is configured. React does not implement a Python `LlmClient`.

For A2A consultation, React reuses the Java capability module as provided. [java_runtime.py](react_agent/ccrs/java_runtime.py) resolves the `ccrs-a2a` runtime jars when the module is requested. [contingency_ccrs.py](react_agent/ccrs/contingency/contingency_ccrs.py) can create Java `ContingencyCcrs` through `ContingencyCcrsFactory.withDefaultsAndDiscoveredProviders()` when `discover_strategy_providers=True`. With `modules=("ccrs-core", "ccrs-a2a")`, Java `ServiceLoader` discovers [A2aConsultationStrategyProvider.java](../ccrs-bdi/ccrs-a2a/src/main/java/ccrs/capabilities/a2a/A2aConsultationStrategyProvider.java) and registers `ConsultationStrategy` with the Java A2A channel. React does not implement an A2A channel in Python.

### Package F: Audit And Experiment Inspection (In-Progress)

This package keeps contingency behavior auditable. The current contingency boundary logs runtime readiness, provider-discovery state, registered strategies, evaluation input fields, strategy-selection policy, returned trace id, evaluation count, suggestion and no-help counts, opportunistic-guidance count, top suggestion, and stop flag. Remaining audit work belongs to Packages C and D: graph-cycle activation reason, routing decisions, prompt-surfacing correlation keys, and consumed guidance markers still need to be emitted once contingency graph routing exists.

The audit surface should distinguish React adapter events from Java CCRS library events, following the existing `[REACT-CCRS-EVENT] event=react.ccrs...` pattern for React-side logs and the Java companion log for Java library behavior.

## Plan of Work

First, preserve the current opportunistic CCRS implementation and avoid broad rewrites. Keep `react_agent/ccrs/java_runtime.py` as the owner of shared Maven/Gradle classpath resolution, JPype startup, and Java logging. Keep `react_agent/ccrs/rdf_adapter.py` as the only Turtle-to-Python-triple parser. Keep `react_agent/ccrs/opportunistic/vocabulary_matcher.py` as the Java `VocabularyMatcher` wrapper. Keep `react_agent/ccrs/opportunistic/opportunistic.py` as the LangGraph node factory. Keep `react_agent/ccrs/state.py` as the CCRS graph state helper rather than moving the whole application state into the adapter package.

For Package A, keep contingency evaluation under `react_agent/ccrs/contingency/`. Python classes and file names should match the Java CCRS Maven library names where Python naming allows it. Use `situation.py` for Java `Situation`, `ccrs_context.py` for Java `CcrsContext`, `in_memory_ccrs_trace_history.py` for Java `InMemoryCcrsTraceHistory`, and `contingency_ccrs.py` for Java `ContingencyCcrs`. Do not introduce adapter-specific alternative names unless the Java name would be ambiguous or un-Pythonic. Do not wire contingency into graph control until the escalation and routing questions in Packages B-D are settled.

Second, keep validation smoke-oriented. Do not add a dedicated test suite unless the user asks for it. Use short Python commands to verify the adapter boundary: one Java-backed Turtle scan with the default green signifier predicate `https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green`, one invalid-Turtle check that returns `{}` with `reason=invalid_turtle`, and graph-builder checks that both baseline and CCRS graphs still return `CompiledStateGraph`.

Third, keep prompt-path validation lightweight. The important behavior is that `react_agent/nodes/llm_node_ccrs_v2.py` finds the latest tool call IDs from the most recent `AIMessage` and exposes only matching append-only CCRS entries as advisory prompt context. If this logic changes, validate it with a small local smoke command or notebook cell rather than adding formal tests by default.

Fourth, maintain the documentation boundary. `react_agent/ccrs/README.md` is the React CCRS adapter documentation file and should be referenced by the root README and this plan. `PLAN_CCRS_README.md` is the execution plan and should record progress, decisions, discoveries, validation, and future work. `AGENTS.md` should remain concise and should direct future sessions to this plan before complex CCRS work.

Fifth, keep future contingency work message-driven. The first contingency step should derive explicit and semantic contingency situations from the normal LangGraph `messages` state, map those situations into the Java contingency model, evaluate candidate revision strategies, and return contingency suggestions through a separate prompt path. Do not mix contingency behavior into the opportunistic CCRS node, and do not introduce duplicate RDF-memory, HTTP-history, or tool-history state channels unless a concrete adapter boundary requires it.

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

    S:\anaconda\agent\python.exe -c "from react_agent.ccrs.opportunistic.vocabulary_matcher import VocabularyMatcher; matcher=VocabularyMatcher.from_maven_local(); data='@prefix maze: <https://kaefer3000.github.io/2021-02-dagstuhl/vocab#> .\n<http://example.org/cell> maze:green <http://example.org/target> .'; print(matcher.evaluate_turtle(data, context={'tool_call_id':'smoke','tool_name':'http_get','agent_name':'SmokeAgent','cycle':'1'}))"

Expected output includes a dictionary with:

    'type': 'signifier'
    'target': 'http://example.org/target'
    'pattern_id': 'https://kaefer3000.github.io/2021-02-dagstuhl/vocab#green'
    'utility': 0.7
    'tool_call_id': 'smoke'

Confirm the Java-backed contingency Package A boundary maps a failure situation and returns a retry suggestion:

    S:\anaconda\agent\python.exe -c "from react_agent.ccrs.contingency import ContingencyCcrs, Situation, SituationType, InMemoryCcrsContext; ccrs=ContingencyCcrs.from_maven_local(); ctx=InMemoryCcrsContext(agent_id='SmokeAgent'); situation=Situation(type=SituationType.FAILURE, trigger='http_error', target_resource='http://example.org/cells/1', failed_action='GET', error_info={'httpStatus':'503','message':'Service unavailable'}, metadata={'agent_name':'SmokeAgent'}); result=ccrs.evaluate(situation, ctx); print(result['top_suggestion']['strategy_id'] if result['top_suggestion'] else None); print(result['top_suggestion']['action_type'] if result['top_suggestion'] else None); print(len(result['evaluations']), len(result['suggestions']), len(result['no_help'])); print(len(ctx.ccrs_history.getCcrsHistory(25)))"

Expected output begins with:

    retry
    retry
    2 1 0
    1

Check for stale state names before finalizing state-related edits:

    rg -n "number_of_cycles|cycle_timings|scan_turtle|scan_triples|Deprecated compatibility" react_agent README.md

Expected output is empty.

## Validation and Acceptance

The opportunistic CCRS adapter is acceptable when all of the following are true. The package compiles with `S:\anaconda\agent\python.exe -m compileall react_agent`. Both graph builders return `CompiledStateGraph`. A Java-backed Turtle scan returns at least one opportunistic CCRS dictionary for the default green signifier pattern. The scan path emits `[REACT-CCRS-EVENT]` lines for adapter classpath/runtime/evaluation/detection when logging is enabled. A Java-backed scan launched after `setup_logging(...)` creates a `logs/<run>.java.log` companion file with `[JAVA-CCRS]` Java library records. Non-RDF tool output emits `react.ccrs.opportunistic.skipped reason=invalid_turtle` instead of an error stack trace. The `ccrs` state channel remains append-only, and the prompt path filters by latest tool call IDs rather than clearing state. No deprecated runtime aliases named `scan_turtle` or `scan_triples` remain.

The contingency Package A boundary is acceptable when a short local Python command can create `ContingencyCcrs`, `Situation`, and `InMemoryCcrsContext`, call Java `ContingencyCcrs.evaluateWithTrace(...)`, receive a Python trace dictionary with selected suggestions and per-strategy evaluations, and show that the Python context recorded one Java trace. Full graph routing, prompt injection, and escalation policy integration are not part of Package A acceptance.

Full maze success is not required for opportunistic adapter acceptance because it depends on the external maze server and live LLM calls. A later experiment validation can run `python main.py --graph-name graph_opportunistic_ccrs --agent-name "CCRSAgent" --log-level "DEBUG"` once the maze server and OpenAI credentials are available.

## Idempotence and Recovery

The local Maven publishing step in `../ccrs-bdi` is safe to rerun when Java CCRS artifacts change:

    ./gradlew publishToMavenLocal

If the Gradle wrapper needs to download Gradle, it may require network approval in Codex. After publishing, rerun the Java-backed scan command from this plan.

The JPype JVM cannot be restarted inside the same Python process after shutdown, so validation commands should use separate short Python processes. If a JPype classpath mistake occurs, fix `react_agent/ccrs/java_runtime.py` and rerun the command in a new process.

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

Java CCRS library log companion:

    logs/<run>.java.log
    2026-05-27 17:08:31,622 [JAVA-CCRS] ccrs.core.rdf.CcrsVocabulary: Detected simple pattern: ...

Current documentation boundary:

    react_agent/ccrs/README.md is the React CCRS adapter documentation file.
    PLAN_CCRS_README.md is the long-running executable plan.
    AGENTS.md records repository guidance for future Codex sessions.

## Interfaces and Dependencies

The Python interpreter for validation is `S:\anaconda\agent\python.exe`. The default `C:\Python313\python.exe` may not have the required LangChain dependencies.

The root `react_agent/ccrs/__init__.py` should not maintain compatibility exports. Use concrete imports:

    from react_agent.ccrs.state import CcrsAgentState
    from react_agent.ccrs.java_runtime import CcrsJavaRuntime, CcrsJavaRuntimeError, get_default_java_runtime
    from react_agent.ccrs.opportunistic.opportunistic import make_opportunistic_ccrs_node, opportunistic_ccrs_node
    from react_agent.ccrs.opportunistic.vocabulary_matcher import VocabularyMatcher, get_default_vocabulary_matcher
    from react_agent.ccrs.contingency import ContingencyCcrs, Situation, InMemoryCcrsContext, InMemoryCcrsTraceHistory, SituationType, get_default_contingency_ccrs

`CcrsJavaRuntime` in `react_agent/ccrs/java_runtime.py` should provide:

    CcrsJavaRuntime.from_maven_local(...)
    CcrsJavaRuntime.ensure_jvm(...)
    CcrsJavaRuntime.resolve_classpath(...)

`VocabularyMatcher` in `react_agent/ccrs/opportunistic/vocabulary_matcher.py` should provide:

    VocabularyMatcher.from_maven_local(...)
    VocabularyMatcher.evaluate_turtle(content, context=None)
    VocabularyMatcher.evaluate_triples(triples, context=None)

Deprecated compatibility aliases such as `scan_turtle` and `scan_triples` should not be reintroduced.

`ContingencyCcrs` in `react_agent/ccrs/contingency/contingency_ccrs.py` should provide:

    ContingencyCcrs.from_maven_local(...)
    ContingencyCcrs.evaluate(situation, context=None)

The current Package A context boundary in [ccrs_context.py](react_agent/ccrs/contingency/ccrs_context.py) is `InMemoryCcrsContext`. It provides a minimal Java `CcrsContext` proxy with RDF query, current resource, agent id, and CCRS trace-history methods. Its trace store is `InMemoryCcrsTraceHistory` in [in_memory_ccrs_trace_history.py](react_agent/ccrs/contingency/in_memory_ccrs_trace_history.py), matching the Java helper name and Java trace-history method names. Package B derives that context from normal LangGraph messages through [interaction.py](react_agent/ccrs/contingency/interaction.py), which owns Java `Interaction` values and outcome-classifier hooks. Package C must preserve one trace-history instance across contingency cycles for an agent run.

`CcrsAgentState` in `react_agent/ccrs/state.py` should continue to include:

    messages: Annotated[Sequence[BaseMessage], add_messages]
    cycle: dict[str, Any]
    ccrs: Annotated[list[dict[str, Any]], add]

The `cycle` object has `number` and UTC `timestamp`. The `ccrs` list contains dictionaries converted from Java `OpportunisticResult` values. Each opportunistic CCRS dictionary should include `ccrs_type`, `type`, `target`, `pattern_id`, `utility`, `metadata`, and `tool_call_id` when the source tool message has an ID.

The Java dependency is the Maven-local artifact `io.github.stefanmhsg.ccrs:ccrs-core:0.1.0-SNAPSHOT`, plus declared Jena 5.6.0 runtime dependencies resolved by `react_agent/ccrs/java_runtime.py`.

## Revision Notes

2026-05-27: Converted this file from a stale architecture/progress note into a formal ExecPlan. The revision preserves the CCRS adapter direction, updates implementation status for JPype, append-only CCRS state, `cycle` state, and key-value audit logging, and records remaining work as executable milestones with validation commands.

2026-05-27: Updated documentation ownership after user direction. `react_agent/ccrs/README.md` is now the React-specific CCRS adapter documentation file, root `README.md` links there, and `AGENTS.md` records scope-control and CCRS-context guidance for future sessions.

2026-05-27: Updated React adapter log naming after user direction. Python adapter logs now use `[React CCRS][Opportunistic]`, and adapter audit events use `[REACT-CCRS-EVENT] event=react.ccrs...` so they can be separated from Java CCRS library events.

2026-05-27: Updated invalid RDF handling after log analysis. Non-Turtle tool outputs are now skipped with `reason=invalid_turtle` instead of being logged as opportunistic CCRS evaluation failures.

2026-05-27: Added Java CCRS companion logging after user direction. `setup_logging(...)` now publishes per-run log paths, and `react_agent.ccrs.java_logging` configures Java JUL records from `ccrs-core` into `logs/<run>.java.log`.

2026-05-27: Removed the structured HTTP request/response/failure history task after user direction. Contingency CCRS should operate on the existing LangGraph `messages` state, which already provides the cause-effect trace of tool calls, tool responses, and errors.

2026-05-27: Removed the RDF memory task after user direction. The React CCRS adapter should remain generic and message-driven, using normal LangGraph/ReAct messages as the source of truth instead of introducing custom duplicated memory fields.

2026-05-27: Verified milestones 1-3 as complete after smoke checks and comparison against `ccrs-jacamo` opportunistic features. React covers the shared Java opportunistic scanning boundary, including simple and structural `scanAll(...)` results, while Jason-specific belief-base and prioritization behavior remain intentionally out of scope.

2026-05-27: Added an in-progress contingency CCRS design discussion. The notes capture current ambiguity around situation types, escalation triggers, current-resource semantics, Java strategy selection, `CcrsContext.query(...)`, trace history, state splitting, correlation, stop behavior, and later LLM/A2A capability integration.

2026-05-27: Added contingency CCRS workpackages for adapter boundary mappings, React evaluation-function mapping, escalation-mode hooks, decision-node routing, a possible unified `ccrs_node`, cycle-correlated contingency activation state, stronger contingency prompt injection, and improved opportunistic-guidance correlation.

2026-05-27: Regrouped the contingency CCRS design discussion into emerging packages: Java contingency bridge, React `CcrsContext` from messages, escalation and graph routing, CCRS node/state/prompt/correlation, optional capability integrations, and audit/experiment inspection.

2026-05-29: Started Package A implementation. `react_agent/ccrs/opportunistic.py` was split into `react_agent/ccrs/opportunistic/opportunistic.py`, direct imports were updated to the new concrete module path, and a new `react_agent/ccrs/contingency/` package now exposes the Java contingency boundary without wiring it into graph routing.

2026-05-29: Started Package B implementation. `InMemoryCcrsContext.from_messages(...)` now derives RDF query triples and Java `Interaction` records from normal LangGraph messages, and React HTTP tools request RDF error bodies from MaSE by default so parseable error responses can participate in `query(...)`. HTTP API responses stay as raw tool content; only actual tool invocation failures are marked as tool errors by the React tool node. `react_agent/ccrs/contingency/interaction.py` now owns Java `Interaction` derivation and exposes an optional outcome-classifier hook for scenario-specific policies.

2026-05-29: Settled the trace-history storage direction for Package B. React uses adapter-owned `InMemoryCcrsTraceHistory` with Java-aligned method names. The future graph routing work must keep that trace-history object alive across contingency CCRS cycles.

2026-05-29: Updated the Contingency CCRS Design Discussion package statuses. Packages A, B, and E are marked complete, Packages C and D remain open, and Package F is marked in-progress until graph routing and prompt-surfacing audit events exist.
