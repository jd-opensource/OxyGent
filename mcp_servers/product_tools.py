"""Product information tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

NAME_TO_ID = {
    "Product A": "PROD001",
    "Product B": "PROD002",
    "Product C": "PROD003",
}

PRODUCTS = {
    "PROD001": {
        "product_id": "PROD001",
        "name": "Product A",
        "price": 5999,
        "description": "High-end smart device equipped with an advanced processor and multifunctional camera system.",
        "category": "Electronics",
        "brand": "Brand A",
        "rating": 4.8,
        "reviews_count": 15420,
    },
    "PROD002": {
        "product_id": "PROD002",
        "name": "Product B",
        "price": 12999,
        "description": "Professional-grade portable device with a high-performance chip, high-definition display, and large storage capacity.",
        "category": "Computing Devices",
        "brand": "Brand A",
        "rating": 4.9,
        "reviews_count": 8760,
    },
    "PROD003": {
        "product_id": "PROD003",
        "name": "Product C",
        "price": 899,
        "description": "Practical and cost-effective product suitable for daily use.",
        "category": "Accessories",
        "brand": "Brand B",
        "rating": 4.5,
        "reviews_count": 23150,
    },
}


@mcp.tool(description="Get product information by product ID")
def get_product_info(product_id: str = Field(description="product ID")) -> dict:
    if product_id not in PRODUCTS:
        if product_id in NAME_TO_ID:
            product_id = NAME_TO_ID[product_id]
        else:
            return {"error": "Product not found"}
    return PRODUCTS.get(product_id, {"error": "Product not found"})


@mcp.tool(description="Get product list by category")
def get_products_by_category(
    category: str = Field(description="Product category"),
) -> list:
    result = [p for p in PRODUCTS.values() if p["category"] == category]
    if not result:
        return [{"message": "No products found in this category"}]
    return result


if __name__ == "__main__":
    mcp.run()
