# CCRS ReAct Adapter

This package contains the Python glue layer that equips LangGraph/ReAct agents
with CCRS capabilities while keeping the Java `ccrs-core` library as the source
of CCRS behavior.

The baseline ReAct graph is intentionally free of imports, state keys, and
prompt variables from this package. Use this adapter only in CCRS-specific graph
variants.

## Current Scope

The implemented scope is opportunistic CCRS:

```text
ToolMessage Turtle
-> rdflib RDF triples
-> Java RdfTriple values
-> Java VocabularyMatcher.scanAll(...)
-> Python CCRS annotation dictionaries
-> LangGraph ccrs state channel
```

The public one-line import target is:

```python
from react_agent.ccrs import opportunistic_ccrs_node
```

## Files

- [runtime.py](runtime.py) starts/configures the JPype JVM, resolves the local
  Maven/Gradle classpath, creates the Java `VocabularyMatcher`, and converts
  Java opportunistic CCRS results back to Python dictionaries.
- [rdf_adapter.py](rdf_adapter.py) converts Turtle text into lightweight Python
  RDF triple values before they are passed into Java.
- [opportunistic.py](opportunistic.py) provides LangGraph node factories for
  opportunistic CCRS.
- [state.py](state.py) provides the reusable CCRS-aware LangGraph state shape.
- [__init__.py](__init__.py) exposes compact public imports while keeping
  heavy dependencies lazy.

## Logging And Naming

Log lines emitted by this package start with `[Opportunistic CCRS]`. Keep this
prefix for all opportunistic CCRS behavior so Python logs remain searchable and
can be correlated with Java CCRS library logs.

The JPype runtime configures Java CCRS logger levels for verbose output. If
Java library messages do not appear in the Python run log, add a dedicated
Java-to-Python logging bridge before expanding contingency CCRS.

Use the names `opportunistic CCRS` and `contingency CCRS` consistently when
describing CCRS approaches. Terms such as observation node, scanner, error
handling, or recovery may describe implementation details, but they should not
replace the CCRS approach name in user-facing documentation or logs.
