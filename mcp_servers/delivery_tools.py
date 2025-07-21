# mcp_servers/delivery_tools.py
"""Delivery management tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

DELIVERY_INFO = {
    "ORDER001": {
        "order_id": "ORDER001",
        "delivery_method": "Standard Delivery",
        "delivery_address": "Street A, District A, City A",
        "delivery_phone": "xxx****xxxx",
        "delivery_time_slot": "09:00-18:00",
        "special_instructions": "Please deliver to the front desk",
        "delivery_fee": 0,
        "estimated_delivery": "2024-01-17 18:00:00",
        "delivery_status": "In Transit",
    },
    "ORDER002": {
        "order_id": "ORDER002",
        "delivery_method": "Next Day Delivery",
        "delivery_address": "Street X, Commercial Area D, City C",
        "delivery_phone": "xxx****xxxx",
        "delivery_time_slot": "10:00-12:00",
        "special_instructions": "Recipient signature required",
        "delivery_fee": 15,
        "estimated_delivery": "2024-01-16 12:00:00",
        "delivery_status": "Delivered",
    },
}


@mcp.tool(description="Retrieve delivery information based on order ID")
def get_delivery_info(order_id: str = Field(description="Order ID")) -> dict:
    """
    Retrieve the delivery information for a specific order.

    Args:
        order_id (str): The order ID to query.

    Returns:
        dict: Delivery information if the order exists, otherwise an error message.
    """
    if order_id in DELIVERY_INFO:
        return DELIVERY_INFO[order_id]
    else:
        return {
            "error": f"Delivery information for order ID {order_id} does not exist."
        }


@mcp.tool(description="Get available delivery methods based on city and package weight")
def get_delivery_methods(
    city: str = Field(description="Recipient city"),
    weight: float = Field(description="Package weight (kg)", default=1.0),
) -> list:
    """
    Retrieve available delivery methods for a given city and package weight.

    Args:
        city (str): The recipient city.
        weight (float): The weight of the package in kilograms.

    Returns:
        dict: Available delivery methods with details for the specified city and weight.
    """

    major_cities = [
        "Province A",
        "Province B",
        "Province C",
        "Province D",
        "Province E",
        "Province F",
        "Province G",
        "Province H",
    ]

    methods = [
        {
            "method": "Standard Delivery",
            "description": "Delivered within 3-5 business days",
            "fee": 0 if weight <= 5 else (weight - 5) * 2,
            "available": True,
        },
        {
            "method": "Express Delivery",
            "description": "Delivered within 1-2 business days",
            "fee": 15 + (0 if weight <= 3 else (weight - 3) * 3),
            "available": city in major_cities,
        },
        {
            "method": "Next Day Delivery",
            "description": "Delivered the next business day (weekdays only)",
            "fee": 25 + (0 if weight <= 2 else (weight - 2) * 5),
            "available": city in major_cities[:4],
        },
        {
            "method": "Same Day Delivery",
            "description": "Delivered on the same day (limited areas only)",
            "fee": 35,
            "available": city in ["Province A", "Province B"] and weight <= 3,
        },
    ]

    # Return only available delivery methods
    available_methods = [m for m in methods if m["available"]]

    return {"city": city, "weight": weight, "available_methods": available_methods}


if __name__ == "__main__":
    mcp.run()
