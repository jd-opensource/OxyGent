import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append('..')

from pydantic import Field
import logging
logger = logging.getLogger(__name__)
from typing import Any
from oxygent import oxy
import requests

gwm = oxy.FunctionHub(name="get_wayback_machine_url_tool", timeout=900)


@gwm.tool(description="get url from wayback machine")
def get_wayback_machine_url_api(
    url: Any = Field(description="The target url"),
    timestamp: Any = Field(description="date, Format: YYYYMMDD, e.g. 20010101")
) -> str:
    way_url = "https://archive.org/wayback/available"
    params = {
        "url": url,
        "timestamp": timestamp
    }

    try:
        response = requests.get(way_url, params=params)
        response.raise_for_status()
        data = response.json()
        if len(data['archived_snapshots']) == 0:
            return "Not found the url page"
        final_url = data['archived_snapshots']['closest']['url']
        return final_url
    except requests.exceptions.RequestException as e:
        return f"error: {e}"


if __name__ == "__main__":
    # mcp.run(transport='sse')
    print("running")


