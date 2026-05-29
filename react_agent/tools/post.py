from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from typing import Mapping
import requests

RDF_ACCEPT = "text/turtle, text/plain;q=0.1"


class PostInput(BaseModel):
    url:str = Field(description="The URL to perform the POST request on")
    data:str = Field(description="The data to include in the POST request body")
    headers:Mapping[str, str] = Field(default=None, description="Optional headers to include in the POST request")


@tool("http_post", args_schema=PostInput)
def http_post(url: str, data: str, config: RunnableConfig, headers: Mapping[str, str] = None) -> str:
    """Post data to a URL."""
    configuration = config.get("configurable", {})
    agent_name = configuration.get("agent_name", "React")
    headers = _request_headers(agent_name, headers)
    r = requests.post(url, data=data, headers=headers, timeout=30)
    return r.text


def _request_headers(agent_name: str, headers: Mapping[str, str] = None) -> dict[str, str]:
    merged = dict(headers or {})
    merged.setdefault("Accept", RDF_ACCEPT)
    merged["Authorization"] = f"Agent {agent_name}"
    return merged
