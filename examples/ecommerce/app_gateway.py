from oxygent import MAS, Config, OxyRequest, oxy
from oxygent.utils.env_utils import get_env_var

Config.set_server_port(8085)


# Workflow function for canceling orders
async def cancel_order_workflow(oxy_request: OxyRequest):
    """
    Cancel order workflow function that handles the complex process of order cancellation,
    including verifying order status, recording cancellation reasons, updating order status, etc.
    First calls the order_agent to invoke the cancel_order tool,
    Then retrieves the original order's item and quantity,
    Then calls the product_agent to invoke the release_reserved_stock tool to update inventory,
    Finally, writes the cancelled order to a local cancelled_orders.json file.
    """
    # Call order_agent to cancel the order
    order_oxy_response = await oxy_request.call(
        callee="order_agent",
        arguments={
            "query": oxy_request.get_query()
            + "\n"
            + f"user query: {oxy_request.get_query(master_level=True)}"
        },
    )
    print("order_agent response:", order_oxy_response.output)

    # Call product_agent to release reserved stock
    product_oxy_response = await oxy_request.call(
        callee="product_agent",
        arguments={
            "query": oxy_request.get_query()
            + "\n"
            + f"order_agent response: {order_oxy_response.output}"
        },
    )

    print("product_agent response:", product_oxy_response.output)
    return f"Order cancelled successfully. Order details: {order_oxy_response.output}, Inventory update: {product_oxy_response.output}"


# Function to merge user and current queries
def update_query(oxy_request: OxyRequest):
    user_query = oxy_request.get_query(master_level=True)
    current_query = oxy_request.get_query()
    oxy_request.set_query(
        f"user query is {user_query}\ncurrent query is {current_query}"
    )
    return oxy_request


oxy_space = [
    # Register the LLM
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
    ),
    # Workflow agent for order cancellation
    oxy.WorkflowAgent(
        name="cancel_order_workflow",
        desc="Order cancellation workflow agent that handles the complex cancellation process, including verifying order status, logging reasons, and updating status.",
        llm_model="default_llm",
        sub_agents=["order_agent", "product_agent"],
        func_workflow=cancel_order_workflow,
        trust_mode=True,
        timeout=20,
    ),
    # Main gateway agent
    oxy.ReActAgent(
        name="gateway_agent",
        is_master=True,
        sub_agents=[
            "order_agent",
            "product_agent",
            "logistics_agent",
            "cancel_order_workflow",
        ],
        llm_model="default_llm",
    ),
    # Remote agent: Product and inventory management
    oxy.SSEOxyGent(
        name="product_agent",
        desc="Product and inventory management agent offering detailed product info: item queries, keyword search, category browsing, and inventory functions such as stock checking, availability validation, warehouse distribution, low-stock alerts, and intelligent restocking suggestions. Important constraint: specific task must be specified when calling this agent.",
        server_url="http://127.0.0.1:8080",
        func_process_input=update_query,
    ),
    # Remote agent: Order management
    oxy.SSEOxyGent(
        name="order_agent",
        desc="Order and payment management agent, specializing in full order lifecycle management: query order details, user order history; integrated with payment services for payment status and method inquiries. Important constraint: specific task must be specified when calling this agent.",
        server_url="http://127.0.0.1:8081",
        func_process_input=update_query,
    ),
    # Remote agent: Logistics
    oxy.SSEOxyGent(
        name="logistics_agent",
        desc="Logistics and delivery agent providing end-to-end services: real-time tracking of packages, order shipment status queries, delivery info management, and shipping method recommendation/cost calculation based on city and weight. Important constraint: specific task must be specified when calling this agent.",
        server_url="http://127.0.0.1:8083",
        func_process_input=update_query,
    ),
]


# Main entry point for starting the web service
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Because the user doesn't want it anymore, so to cancel ORDER003 order, please help me cancel this order",
        )


# Launch the main function
if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
