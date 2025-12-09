from .get import http_get
from .post import http_post

tools = [http_get, http_post]
tools_by_name = {t.name: t for t in tools}
