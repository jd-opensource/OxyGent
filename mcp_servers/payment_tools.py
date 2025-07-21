"""Payment tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

ORDER_TO_PAYMENT = {"ORDER001": "PAY001", "ORDER002": "PAY002"}

PAYMENTS = {
    "PAY001": {
        "payment_id": "PAY001",
        "order_id": "ORDER001",
        "amount": 5999.00,
        "payment_method": "Pay method A",
        "status": "Paid",
        "transaction_id": "2024011510300001",
        "create_time": "2024-01-15 10:30:00",
        "paid_time": "2024-01-15 10:30:15",
    },
    "PAY002": {
        "payment_id": "PAY002",
        "order_id": "ORDER002",
        "amount": 12999.00,
        "payment_method": "Pay method B",
        "status": "Paid",
        "transaction_id": "2024011510310002",
        "create_time": "2024-01-16 14:20:00",
        "paid_time": "2024-01-16 14:20:20",
    },
}


@mcp.tool(description="Query payment status by payment ID or order ID")
def query_payment_status(
    id=Field(description="Payment ID or Order ID"),
) -> dict:
    """Query the payment status"""
    if id not in PAYMENTS:
        if id not in ORDER_TO_PAYMENT:
            return {"error": "Payment record or order does not exist"}
        id = ORDER_TO_PAYMENT[id]  # Convert order ID to payment ID
    payment = PAYMENTS[id]
    return payment


@mcp.tool(description="Get supported pay methods")
def get_payment_methods() -> list:
    """Supported pay methods"""
    return [
        {
            "method": "payment method A",
            "fee_rate": 0.006,
            "max_amount": 50000,
            "description": "Balances/Bank Cards",
        },
        {
            "method": "payment method B",
            "fee_rate": 0.006,
            "max_amount": 50000,
            "description": "Cash/Bank Cards",
        },
        {
            "method": "payment method C",
            "fee_rate": 0.008,
            "max_amount": 100000,
            "description": "Bank Cards/Credit Cards",
        },
    ]


if __name__ == "__main__":
    mcp.run()
