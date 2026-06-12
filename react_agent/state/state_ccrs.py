from react_agent.ccrs.state import CcrsAgentState as CcrsLibraryState


class CcrsAgentState(CcrsLibraryState):
    """The state of this agent when the CCRS graph variant is enabled."""

    # Add use-case-specific channels here when this agent needs state beyond the
    # CCRS library contract, for example experiment or scenario-specific fields.
