from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Initialize FastMCP server instance
mcp = FastMCP()


# tools for multi-example
PATHS = {
    #   id        start  end   cost  time(day)
    "p1": dict(s="A", e="B", cost=3, days=4.0),
    "p2": dict(s="A", e="B", cost=4, days=2.0),
    "p3": dict(s="A", e="B", cost=6, days=1.0),
}


@mcp.tool(description="A tool getting the cost of path")
def get_cost(path_id: str = Field(..., description="Path id")) -> float:
    if path_id not in PATHS:
        raise ValueError(f"Unknown {path_id}")
    return PATHS[path_id]["cost"]


@mcp.tool(description="A tool getting the time of path")
def get_time(path_id: str = Field(..., description="Path id")) -> float:
    if path_id not in PATHS:
        raise ValueError(f"Unknown {path_id}")
    return PATHS[path_id]["days"]


@mcp.tool(description="List all of the path ids from A to B")
def get_path_ids(start: str = Field("A"), end: str = Field("B")) -> list[str]:
    return [pid for pid, v in PATHS.items() if v["s"] == start and v["e"] == end]


# ---------------------------------------------------------------

# Entry point: run the MCP server when script is executed directly
if __name__ == "__main__":
    mcp.run()
