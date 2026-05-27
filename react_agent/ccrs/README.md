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

The implemented scope is opportunistic CCRS:

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
from react_agent.ccrs import opportunistic_ccrs_node
```

Contingency CCRS is intentionally not implemented in this package yet. It
should be added only after the opportunistic adapter boundary remains stable
under the smoke-validation commands tracked in the plan.

## Files

- [runtime.py](runtime.py) starts/configures the JPype JVM, resolves the local
  Maven/Gradle classpath, creates the Java `VocabularyMatcher`, and converts
  Java opportunistic CCRS results back to Python dictionaries.
- [rdf_adapter.py](rdf_adapter.py) converts Turtle text into lightweight Python
  RDF triple values before they are passed into Java.
- [opportunistic.py](opportunistic.py) provides LangGraph node factories for
  opportunistic CCRS.
- [state.py](state.py) provides the reusable CCRS-aware LangGraph state shape.
  Its `ccrs` channel appends opportunistic CCRS annotations. Prompt injection
  filters that history by the latest tool call IDs before presenting advisory
  context to the LLM.
- [audit.py](audit.py) emits stable `[REACT-CCRS-EVENT]` key-value log lines
  for React adapter runtime verification.
- [java_logging.py](java_logging.py) configures Java `java.util.logging`
  records from `ccrs-core` into a per-run companion log file.
- [__init__.py](__init__.py) exposes compact public imports while keeping
  heavy dependencies lazy.

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
