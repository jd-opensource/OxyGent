"""
MCP Server for Mathematical Operations

This file demonstrates the structure of math tools that can be invoked by an agent.
It provides mathematical tools using the FastMCP framework.
"""

import math
from decimal import Decimal, getcontext

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Initialize FastMCP server instance
mcp = FastMCP()


@mcp.tool(description="Index tool")
def power(
    n: int = Field(description="base"), m: int = Field(description="index", default=2)
) -> int:
    return math.pow(n, m)


@mcp.tool(description="Pi tool")
def calc_pi(prec: int = Field(description="How many digits after the dot")) -> float:
    """
    Calculate pi using the Chudnovsky algorithm for high precision.

    This implementation uses the Chudnovsky algorithm, which converges very rapidly.
    Each term in the series provides approximately 8 decimal digits of precision.

    Args:
        prec: The number of decimal places to calculate

    Returns:
        float: The value of pi with the specified precision
    """
    getcontext().prec = prec
    x = 0
    for k in range(
        int(prec / 8) + 1
    ):  # Calculate the series: each iteration provides ~8 decimal digits of precision
        a = 2 * Decimal.sqrt(Decimal(2)) / 9801
        b = math.factorial(4 * k) * (1103 + 26390 * k)
        c = pow(math.factorial(k), 4) * pow(396, 4 * k)
        x = x + a * b / c
    return 1 / x


# tools for multi-example
PATHS = {
    #   id        start  end   cost  time(day)
    "p1": dict(s="A", e="B", cost=3, days=1.0),
    "p2": dict(s="A", e="B", cost=4, days=3.0),
    "p3": dict(s="A", e="B", cost=6, days=1.5),
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
