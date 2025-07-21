"""Order management tools."""

from datetime import datetime

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

ORDERS = {
    "ORDER001": {
        "order_id": "ORDER001",
        "user_id": "USER001",
        "products": [
            {"product_id": "PROD001", "name": "Product A", "quantity": 1, "price": 5999}
        ],
        "total": 5999,
        "status": "Shipped",
        "create_time": "2024-01-15 10:30:00",
        "shipping_address": "No. A, Street A, District A, City A",
    },
    "ORDER002": {
        "order_id": "ORDER002",
        "user_id": "USER002",
        "products": [
            {
                "product_id": "PROD002",
                "name": "Product B",
                "quantity": 1,
                "price": 12999,
            }
        ],
        "total": 12999,
        "status": "Delivered",
        "create_time": "2024-01-16 14:20:00",
        "shipping_address": "No. X, Commercial Street, District D, City C",
    },
    "ORDER003": {
        "order_id": "ORDER003",
        "user_id": "USER003",
        "products": [
            {"product_id": "PROD003", "name": "Product C", "quantity": 2, "price": 899},
            {
                "product_id": "PROD001",
                "name": "Product A",
                "quantity": 1,
                "price": 5999,
            },
        ],
        "total": 7797,
        "status": "Pending Payment",
        "create_time": "2024-01-17 09:00:00",
        "shipping_address": "No. B, Street B, District B, City B",
    },
}


@mcp.tool(description="Query order details by order ID")
def query_order(order_id: str = Field(description="Order ID")) -> dict:
    """
    Retrieve order details for a specific order ID.

    Args:
        order_id (str): The order ID to query.

    Returns:
        dict: Order details if found, otherwise an error message.
    """
    if order_id in ORDERS:
        return ORDERS[order_id]
    else:
        return {"error": f"Order ID {order_id} does not exist."}


@mcp.tool(description="Query all orders for a specific user")
def query_user_orders(user_id: str = Field(description="User ID")) -> list:
    """
    Retrieve all orders placed by a specific user.

    Args:
        user_id (str): The user ID.

    Returns:
        list: A list of orders associated with the user.
    """
    user_orders = [order for order in ORDERS.values() if order["user_id"] == user_id]
    if user_orders:
        return user_orders
    else:
        return [{"message": f"user {user_id} has no orders"}]


@mcp.tool(
    description="Cancel a specific order with reason and record the cancellation time"
)
def cancel_order(
    order_id: str = Field(description="Order ID"),
    reason: str = Field(description="Cancellation reason"),
) -> dict:
    """
    Cancel an order, recording the cancellation reason and time.

    Args:
        order_id (str): The order ID to cancel.
        reason (str): The reason for cancellation.

    Returns:
        dict: Cancellation status and details.
    """
    if order_id in ORDERS:
        if ORDERS[order_id]["status"] in ["Processing", "Pending Payment"]:
            ORDERS[order_id]["status"] = "Cancelled"
            ORDERS[order_id]["cancel_reason"] = reason
            ORDERS[order_id]["cancel_time"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            return {
                "success": True,
                "message": f"Order {order_id} has been successfully cancelled. Reason: {reason}",
                "cancel_time": ORDERS[order_id]["cancel_time"],
                "products": ORDERS[order_id]["products"],
                "product_id": [
                    product["product_id"] for product in ORDERS[order_id]["products"]
                ],
            }
        else:
            return {
                "success": False,
                "message": f"Order {order_id} cannot be cancelled due to its current status: {ORDERS[order_id]['status']}.",
            }
    else:
        return {"success": False, "message": f"Order ID {order_id} does not exist."}


if __name__ == "__main__":
    mcp.run()
