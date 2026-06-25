from typing import Any, NotRequired

from react_agent.ccrs.state import CcrsAgentState as CcrsLibraryState


class CcrsAgentState(CcrsLibraryState):
    """The state of this agent when the CCRS graph variant is enabled."""

    current_cell: NotRequired[str | None]
    advertised_navigation_options: NotRequired[dict[str, Any] | None]

    # Add use-case-specific channels here when this agent needs state beyond the
    # CCRS library contract, for example experiment or scenario-specific fields.
