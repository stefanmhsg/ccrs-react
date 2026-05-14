from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RdfTripleValue:
    """Python-side RDF triple value passed into Java opportunistic CCRS."""

    subject: str
    predicate: str
    object: str


def parse_turtle_triples(content: str) -> list[RdfTripleValue]:
    """Parse Turtle text into CCRS core-compatible RDF triple values."""

    # rdflib stays local to parsing so importing the adapter does not require it.
    from rdflib import Graph

    graph = Graph()
    graph.parse(data=content, format="turtle")
    return [
        RdfTripleValue(subject=str(subject), predicate=str(predicate), object=str(object_))
        for subject, predicate, object_ in graph
    ]
