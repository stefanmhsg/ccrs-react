# CCRS ReAct Adapter

This package contains the Python glue layer that equips LangGraph/ReAct agents
with CCRS capabilities while keeping the Java `ccrs-core` library as the source
of CCRS behavior.

The baseline ReAct graph is intentionally free of imports, state keys, and
prompt variables from this package. Use this adapter only in CCRS-specific graph
variants.

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

## Current Scope

The implemented graph-integrated scope is opportunistic CCRS:

```text
ToolMessage Turtle
-> rdflib RDF triples
-> Java RdfTriple values
-> Java VocabularyMatcher.scanAll(...)
-> Python CCRS annotation dictionaries
-> append-only LangGraph ccrs state channel
```

The public one-line import target is:

```python
from react_agent.ccrs.opportunistic.opportunistic import opportunistic_ccrs_node
```

The implemented contingency scope is the Python-to-Java adapter boundary:

```text
Python Situation
-> Java Situation
-> Java CcrsContext proxy
-> Java ContingencyCcrs.evaluateWithTrace(...)
-> Python contingency trace and strategy-result dictionaries
```

The contingency boundary can also reuse Java optional capability modules
through `ServiceLoader`. For LLM prediction, create the wrapper with
`modules=("ccrs-core", "ccrs-langchain4j")` and
`discover_strategy_providers=True`; Java then registers
`Langchain4jPredictionStrategyProvider` and `PredictionLlmStrategy` when
`OPENAI_API_KEY` or `LLM_API_KEY` is configured. For A2A consultation, add
`"ccrs-a2a"` to the modules tuple; Java then registers the provided
`A2aConsultationStrategyProvider` and `ConsultationStrategy`.

Contingency CCRS is not wired into a LangGraph node or decision route yet. The
next design step is deciding when an agent escalates to contingency CCRS and
how authoritative contingency suggestions affect graph control.

## Files

- [java_runtime.py](java_runtime.py) contains the shared Maven/Gradle
  classpath resolver, JPype startup, and Java logging setup.
- [rdf_adapter.py](rdf_adapter.py) converts Turtle text into lightweight Python
  RDF triple values before they are passed into Java.
- [opportunistic/vocabulary_matcher.py](opportunistic/vocabulary_matcher.py)
  wraps Java `VocabularyMatcher` and converts Java opportunistic CCRS results
  to Python dictionaries.
- [opportunistic/opportunistic.py](opportunistic/opportunistic.py) provides
  LangGraph node factories for opportunistic CCRS.
- [contingency/situation.py](contingency/situation.py) defines the Python
  `Situation` object and `SituationType` names that map to Java `Situation`
  and `Situation.Type`.
- [contingency/ccrs_context.py](contingency/ccrs_context.py) provides a
  minimal in-memory Java `CcrsContext` proxy.
- [contingency/in_memory_ccrs_trace_history.py](contingency/in_memory_ccrs_trace_history.py)
  provides an in-memory `InMemoryCcrsTraceHistory` store.
- [contingency/contingency_ccrs.py](contingency/contingency_ccrs.py) loads
  Java contingency CCRS, calls `ContingencyCcrs.evaluateWithTrace(...)`,
  records traces on the Python context, and converts Java strategy results into
  Python dictionaries. It can create core-only Java CCRS instances or ask Java
  `ContingencyCcrsFactory` to register optional `ServiceLoader` strategy
  providers visible on the JPype classpath.
- [state.py](state.py) provides the reusable CCRS-aware LangGraph state shape.
  Its `ccrs` channel appends opportunistic CCRS annotations. Prompt injection
  filters that history by the latest tool call IDs before presenting advisory
  context to the LLM.
- [audit.py](audit.py) emits stable `[REACT-CCRS-EVENT]` key-value log lines
  for React adapter runtime verification.
- [java_logging.py](java_logging.py) configures Java `java.util.logging`
  records from `ccrs-core` into a per-run companion log file.
- [__init__.py](__init__.py) marks the package. Adapter code should import from
  concrete modules instead of relying on root-package re-exports.

## Logging And Naming

Human-readable log lines emitted by this package start with
`[React CCRS][Opportunistic]`. Keep this prefix for all React-side
opportunistic CCRS behavior so Python adapter logs remain searchable and can be
distinguished from Java CCRS library logs.

Auditable lifecycle events use the React-adapter-specific
`[REACT-CCRS-EVENT]` prefix. Java library events can continue using
`[CCRS-EVENT]`. For opportunistic CCRS, the important React adapter event names
are:

- `react.ccrs.opportunistic.evaluate`
- `react.ccrs.opportunistic.detected`
- `react.ccrs.opportunistic.cycle_annotations`
- `react.ccrs.opportunistic.no_annotations`
- `react.ccrs.opportunistic.skipped`
- `react.ccrs.opportunistic.failed`

Invalid or non-RDF tool output should be logged as
`react.ccrs.opportunistic.skipped reason=invalid_turtle`, not as a CCRS
runtime failure. This is expected for tool responses such as successful
`http_post` acknowledgements that are not Turtle observations.

For contingency CCRS boundary calls, the current React adapter event names are:

- `react.ccrs.contingency.classpath.resolved`
- `react.ccrs.contingency.jvm.start`
- `react.ccrs.contingency.runtime.ready`
- `react.ccrs.contingency.evaluate`
- `react.ccrs.contingency.returned`

The JPype runtime configures Java CCRS logger levels for verbose output. If
the React run log is `logs/<run>.log`, Java CCRS library messages are written
to the companion file `logs/<run>.java.log`. The companion file uses the
`[JAVA-CCRS]` prefix and captures Java library events such as vocabulary
loading, pattern compilation, matches, warnings, and Java-side `[CCRS-EVENT]`
records. Keeping Java logs in a companion file avoids cross-runtime file
handler conflicts while preserving the same run name for experiment analysis.

Use the names `opportunistic CCRS` and `contingency CCRS` consistently when
describing CCRS approaches. Terms such as observation node, scanner, error
handling, or recovery may describe implementation details, but they should not
replace the CCRS approach name in user-facing documentation or logs.
