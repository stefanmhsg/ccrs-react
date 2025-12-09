from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Mapping
import requests

class GetInput(BaseModel):
    url:str = Field(description="The URL to perform the GET request on")
    headers:Mapping[str, str] = Field(default=None, description="Optional headers to include in the GET request")


@tool("http_get", args_schema=GetInput)
def http_get(url: str, headers: Mapping[str, str] = None) -> str:
    """Dereferece a URI. Returns text/turtle."""
    try:
        default = {"Authorization" : "Agent React"}
        if headers:
            headers = {**headers, **default}  # Custom headers first, then default (default overwrites)
        else:
            headers = default
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return {
            "error": True,
            "message": f"GET request failed for {url}. Error: {str(e)}"
        }
