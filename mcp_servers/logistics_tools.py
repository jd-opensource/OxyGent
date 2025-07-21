# mcp_servers/logistics_tools.py
"""Logistics tracking tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

COURIER_COMPANIES = {
    "JD": "JD Logistics",
}

TRACKING_DATA = {
    "JD1234567890": {
        "tracking_number": "JD1234567890",
        "courier_company": "JD",
        "order_id": "ORDER001",
        "sender": {
            "name": "Seller A",
            "address": "Tech Park, District A, Province A",
            "phone": "xxx-xxx-xxxx",
        },
        "receiver": {
            "name": "Recipient A",
            "address": "No. A, Street A, District A, City A",
            "phone": "xxx****xxxx",
        },
        "status": "In Transit",
        "estimated_delivery": "2024-01-17 18:00:00",
        "tracking_history": [
            {
                "time": "2024-01-15 14:30:00",
                "location": "District A, City A, Province A",
                "status": "Shipped",
                "description": "Your package has been shipped from [City A District A Branch].",
            },
            {
                "time": "2024-01-15 18:45:00",
                "location": "City A, Province A",
                "status": "In Transit",
                "description": "Package arrived at [City A Transfer Center].",
            },
            {
                "time": "2024-01-16 08:30:00",
                "location": "City B",
                "status": "In Transit",
                "description": "Package arrived at [City B Transfer Center].",
            },
            {
                "time": "2024-01-16 15:20:00",
                "location": "District B, City B",
                "status": "Out for Delivery",
                "description": "Package arrived at [City B District B Branch], delivery is being arranged.",
            },
        ],
    },
    "JD1234567891": {
        "tracking_number": "JD1234567891",
        "courier_company": "JD",
        "order_id": "ORDER002",
        "sender": {
            "name": "Seller B",
            "address": "Tech Park, District C, City C",
            "phone": "xxx-xxx-xxxx",
        },
        "receiver": {
            "name": "Recipient B",
            "address": "No. X, Commercial Street, District D, City C",
            "phone": "xxx****xxxx",
        },
        "status": "Delivered",
        "estimated_delivery": "2024-01-16 12:00:00",
        "actual_delivery": "2024-01-16 11:30:00",
        "tracking_history": [
            {
                "time": "2024-01-15 20:00:00",
                "location": "District C, City C",
                "status": "Shipped",
                "description": "Your item has left the warehouse.",
            },
            {
                "time": "2024-01-16 06:00:00",
                "location": "City C",
                "status": "In Transit",
                "description": "Item has arrived at the delivery station.",
            },
            {
                "time": "2024-01-16 09:30:00",
                "location": "District D, City C",
                "status": "Out for Delivery",
                "description": "Courier [Courier A xxx****xxxx] is delivering your package.",
            },
            {
                "time": "2024-01-16 11:30:00",
                "location": "No. X, Commercial Street, District D, City C",
                "status": "Delivered",
                "description": "Your package has been delivered. Signed by: Recipient.",
            },
        ],
    },
}


@mcp.tool(description="Retrieve logistics tracking information by tracking number")
def track_package(tracking_number: str = Field(description="Tracking number")) -> dict:
    """
    Retrieve tracking information for a package based on its tracking number.

    Args:
        tracking_number (str): The tracking number of the package.

    Returns:
        dict: Tracking information if found, otherwise an error message with suggestion.
    """
    if tracking_number in TRACKING_DATA:
        tracking_info = TRACKING_DATA[tracking_number].copy()
        # Add courier company name
        tracking_info["courier_name"] = COURIER_COMPANIES.get(
            tracking_info["courier_company"], "Unknown courier company"
        )
        return tracking_info
    else:
        return {
            "error": f"Tracking number {tracking_number} does not exist or is not yet in the system.",
            "suggestion": "Please check the tracking number for accuracy or try again later.",
        }


@mcp.tool(description="Retrieve logistics tracking information by order ID")
def track_by_order(order_id: str = Field(description="Order ID")) -> list:
    """
    Retrieve all tracking information associated with a specific order ID.

    Args:
        order_id (str): The order ID to query.

    Returns:
        list: List of tracking information dictionaries if found, otherwise an error message.
    """
    results = []
    for tracking_info in TRACKING_DATA.values():
        if tracking_info["order_id"] == order_id:
            info = tracking_info.copy()
            info["courier_name"] = COURIER_COMPANIES.get(
                info["courier_company"], "Unknown courier company"
            )
            results.append(info)

    if results:
        return results
    else:
        return [{"error": f"No tracking information found for order ID {order_id}."}]


if __name__ == "__main__":
    mcp.run()
