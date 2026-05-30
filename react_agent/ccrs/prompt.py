"""Default prompt text for injecting CCRS context into React agents."""

from __future__ import annotations


DEFAULT_CCRS_SYSTEM_PROMPT = (
    "Course Check and Revision Strategy (CCRS) context is provided below as JSON. "
    "Use it according to the channel semantics: opportunistic annotations are advisory; "
    "contingency CCRS entries are recovery guidance for the current situation; "
    "contingency-produced opportunistic guidance are recovery guidance for the current situation that may span multiple steps.\n\n"
    "{ccrs}"
)
