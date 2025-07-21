# mcp_servers/inventory_tools.py
"""Inventory management tools."""

from datetime import datetime

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

NAME_TO_ID = {
    "Product A": "PROD001",
    "Product B": "PROD002",
    "Product C": "PROD003",
}

INVENTORY = {
    "PROD001": {
        "product_id": "PROD001",
        "product_name": "Product A",
        "total_stock": 1500,
        "available_stock": 1200,
        "reserved_stock": 300,  # Prevents reserved stock from being sold
        "warehouse_locations": {
            "Warehouse A": 400,
            "Warehouse B": 500,
            "Warehouse C": 300,
            "Warehouse D": 0,
        },
        "low_stock_threshold": 100,
        "last_restock_date": "2024-01-10",
        "supplier": "Supplier A",
    },
    "PROD002": {
        "product_id": "PROD002",
        "product_name": "Product B",
        "total_stock": 800,
        "available_stock": 650,
        "reserved_stock": 150,
        "warehouse_locations": {
            "Warehouse A": 200,
            "Warehouse B": 300,
            "Warehouse C": 150,
            "Warehouse D": 0,
        },
        "low_stock_threshold": 50,
        "last_restock_date": "2024-01-08",
        "supplier": "Supplier A",
    },
    "PROD003": {
        "product_id": "PROD003",
        "product_name": "Product C",
        "total_stock": 3000,
        "available_stock": 2800,
        "reserved_stock": 200,
        "warehouse_locations": {
            "Warehouse A": 800,
            "Warehouse B": 1000,
            "Warehouse C": 700,
            "Warehouse D": 300,
        },
        "low_stock_threshold": 500,
        "last_restock_date": "2024-01-12",
        "supplier": "Supplier B",
    },
}


@mcp.tool(description="Query inventory info by product ID or name")
def check_inventory(product_id: str = Field(description="Product ID or name")) -> dict:
    """Query detailed inventory info for a specific product."""
    if product_id not in INVENTORY:
        if product_id in NAME_TO_ID:
            product_id = NAME_TO_ID[product_id]
        else:
            return {"error": f"Product ID or name {product_id} does not exist."}

    inventory_info = INVENTORY[product_id].copy()
    # Add stock status
    if inventory_info["available_stock"] <= inventory_info["low_stock_threshold"]:
        inventory_info["stock_status"] = "Low Stock Warning"
    elif inventory_info["available_stock"] == 0:
        inventory_info["stock_status"] = "Out of Stock"
    else:
        inventory_info["stock_status"] = "Sufficient Stock"

    return inventory_info


@mcp.tool(
    description="Check if the specified quantity of a product is available in stock"
)
def check_stock_availability(
    product_id: str = Field(description="Product ID or name"),
    quantity: int = Field(description="Required quantity"),
) -> dict:
    """
    Check if there is sufficient stock to fulfill an order.

    Returns:
        dict: Availability status and details.
    """
    if product_id not in INVENTORY:
        if product_id in NAME_TO_ID:
            product_id = NAME_TO_ID[product_id]
        else:
            return {"error": f"Product ID or name {product_id} does not exist."}

    inventory = INVENTORY[product_id]
    available_stock = inventory["available_stock"]

    if quantity <= available_stock:
        return {
            "available": True,
            "requested_quantity": quantity,
            "available_stock": available_stock,
            "message": f"Sufficient stock available to fulfill the order of {quantity} units.",
        }
    else:
        return {
            "available": False,
            "requested_quantity": quantity,
            "available_stock": available_stock,
            "shortage": quantity - available_stock,
            "message": f"Insufficient stock: requested {quantity}, only {available_stock} available.",
        }


@mcp.tool(description="Release reserved stock (called when an order is canceled)")
def release_reserved_stock(
    product_id: str = Field(description="Product ID or name"),
    quantity: int = Field(description="Quantity to release"),
    order_id: str = Field(description="Order ID"),
) -> dict:
    """
    Release reserved stock for a canceled order.

    Returns:
        dict: Release status and updated available stock.
    """
    if product_id not in INVENTORY:
        if product_id in NAME_TO_ID:
            product_id = NAME_TO_ID[product_id]
        else:
            return {"success": False, "message": "Product does not exist."}

    inventory = INVENTORY[product_id]

    if quantity > inventory["reserved_stock"]:
        return {
            "success": False,
            "message": f"Insufficient reserved stock to release {quantity} units.",
        }

    inventory["reserved_stock"] -= quantity
    inventory["available_stock"] += quantity

    return {
        "success": True,
        "message": f"Released {quantity} units of {inventory['product_name']} for order {order_id}.",
        "available_stock": inventory["available_stock"],
    }


@mcp.tool(description="Get a list of all low stock products")
def get_low_stock_products() -> list:
    """
    Retrieve a list of products with stock below their threshold.

    Returns:
        list: List of products with low stock.
    """
    low_stock_items = []

    for product_id, inventory in INVENTORY.items():
        if inventory["available_stock"] <= inventory["low_stock_threshold"]:
            low_stock_items.append(
                {
                    "product_id": product_id,
                    "product_name": inventory["product_name"],
                    "available_stock": inventory["available_stock"],
                    "low_stock_threshold": inventory["low_stock_threshold"],
                    "urgency": "Critical"
                    if inventory["available_stock"] == 0
                    else "Warning",
                }
            )

    if not low_stock_items:
        return [{"message": "No products with low stock."}]
    return low_stock_items


@mcp.tool(description="Query inventory distribution by warehouse")
def get_inventory_by_warehouse(
    warehouse: str = Field(description="Warehouse name"),
) -> dict:
    """
    Retrieve the inventory distribution for all products in a specific warehouse.

    Returns:
        dict: Products and their stock in the given warehouse.
    """
    warehouse_inventory = {}

    for product_id, inventory in INVENTORY.items():
        if warehouse in inventory["warehouse_locations"]:
            warehouse_inventory[product_id] = {
                "product_name": inventory["product_name"],
                "stock": inventory["warehouse_locations"][warehouse],
                "total_available": inventory["available_stock"],
            }

    return {
        "warehouse": warehouse,
        "products": warehouse_inventory,
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@mcp.tool(description="Get restock suggestions")
def get_restock_suggestions() -> list:
    """
    Generate restock suggestions for products with low stock.

    Returns:
        list: Restock suggestions including recommended quantity and urgency.
    """
    suggestions = []

    for product_id, inventory in INVENTORY.items():
        if inventory["available_stock"] <= inventory["low_stock_threshold"]:
            suggested_quantity = (
                inventory["low_stock_threshold"] * 3 - inventory["total_stock"]
            )

            suggestions.append(
                {
                    "product_id": product_id,
                    "product_name": inventory["product_name"],
                    "current_stock": inventory["available_stock"],
                    "suggested_restock": max(suggested_quantity, 0),
                    "supplier": inventory["supplier"],
                    "priority": "High"
                    if inventory["available_stock"]
                    <= inventory["low_stock_threshold"] // 2
                    else "Medium",
                    "last_restock": inventory["last_restock_date"],
                }
            )

    if not suggestions:
        return [{"message": "Stock levels are sufficient. No restocking needed."}]
    return suggestions


if __name__ == "__main__":
    mcp.run()
