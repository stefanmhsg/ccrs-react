from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from typing import Mapping
import requests

RDF_ACCEPT = "text/turtle, text/plain;q=0.1"


class GetInput(BaseModel):
    url:str = Field(description="The URL to perform the GET request on")
    headers:Mapping[str, str] = Field(default=None, description="Optional headers to include in the GET request")


@tool("http_get", args_schema=GetInput)
def http_get(url: str, config: RunnableConfig, headers: Mapping[str, str] = None) -> str:
    """Dereferece a URI. Returns text/turtle."""
    configuration = config.get("configurable", {})
    agent_name = configuration.get("agent_name", "React")
    headers = _request_headers(agent_name, headers)
    r = requests.get(url, headers=headers, timeout=30)
    return r.text


def _request_headers(agent_name: str, headers: Mapping[str, str] = None) -> dict[str, str]:
    merged = dict(headers or {})
    merged.setdefault("Accept", RDF_ACCEPT)
    merged["Authorization"] = f"Agent {agent_name}"
    return merged
