from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Mapping
import requests

class PostInput(BaseModel):
    url:str = Field(description="The URL to perform the POST request on")
    data:str = Field(description="The data to include in the POST request body")
    headers:Mapping[str, str] = Field(default=None, description="Optional headers to include in the POST request")


@tool("http_post", args_schema=PostInput)
def http_post(url: str, data: str, headers: Mapping[str, str] = None) -> str:
    """Post data to a URL."""
    try:
        default = {"Authorization" : "Agent React"}
        if headers:
            headers = {**headers, **default}  # Custom headers first, then default (default overwrites)
        else:
            headers = default
        r = requests.post(url, data=data, headers=headers, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return {
            "error": True,
            "message": f"POST request failed for {url}. Error: {str(e)}"
        }
