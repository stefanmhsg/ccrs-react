from __future__ import annotations

from dataclasses import dataclass


class CcrsRdfParseError(ValueError):
    """Raised when a tool observation is not parseable RDF/Turtle."""


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
    try:
        graph.parse(data=content, format="turtle")
    except Exception as exc:
        raise CcrsRdfParseError("Tool observation is not valid Turtle RDF.") from exc
    return [
        RdfTripleValue(subject=str(subject), predicate=str(predicate), object=str(object_))
        for subject, predicate, object_ in graph
    ]
