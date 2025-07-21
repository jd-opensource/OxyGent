from pydantic import Field

from oxygent import MAS, Config, OxyRequest, oxy
from oxygent.prompts import INTENTION_PROMPT
from oxygent.utils.env_utils import get_env_var

# Config.set_log_level('INFO')
Config.load_from_json("./config.json", env="default")


async def workflow(oxy_request: OxyRequest):
    short_memory = oxy_request.get_short_memory()
    print("--- History --- :", short_memory)
    master_short_memory = oxy_request.get_short_memory(master_level=True)
    print("--- User-level History --- :", master_short_memory)
    print("user query:", oxy_request.get_query(master_level=True))
    await oxy_request.send_message("msg")
    oxy_response = await oxy_request.call(
        callee="time_agent", arguments={"query": "What time is it now?"}
    )
    print("--- Current Time --- :", oxy_response.output)
    import re

    numbers = re.findall(r"\d+", oxy_request.get_query())
    if numbers:
        n = numbers[-1]
        oxy_response = await oxy_request.call(callee="pi", arguments={"prec": n})
        pi = oxy_response.output
        return f"To {n} decimal places: {pi}"
    else:
        return "To 2 decimal places: 3.14, or you can ask me how many decimal places to keep"


fh = oxy.FunctionHub(name="joke_tools")


@fh.tool(description="A tool that is good at telling jokes")
async def joke_tool(joke_type: str = Field(description="Type of joke")):
    import random

    jokes = [
        "Teacher: 'Xiaoming, make a sentence with “because... therefore...”'\nXiaoming: 'Because the teacher asked me to make a sentence with “because... therefore...”, therefore I made a sentence with “because... therefore...”'",
        "Doctor: 'You have amnesia.'\nPatient: 'What? What do I have?'\nDoctor: 'You have amnesia.'\nPatient: 'What? What do I have?'",
        "Xiaoming asked his mom: 'Mom, why is there a “duck egg” (zero) on my homework notebook?'\nMom: 'Because the teacher thinks your work is quack-tastic!'",
    ]
    print("Joke type", joke_type)
    return random.choice(jokes)


oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
    ),
    oxy.ChatAgent(
        name="intent_agent", prompt=INTENTION_PROMPT, llm_model="default_llm"
    ),
    fh,
    oxy.StdioMCPClient(
        name="time",
        params={
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone=Asia/Shanghai"],
        },
    ),
    oxy.StdioMCPClient(
        name="filesystem",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "./local_file"],
        },
    ),
    oxy.StdioMCPClient(
        name="my_tools",
        params={
            "command": "uv",
            "args": ["--directory", "./mcp_servers", "run", "my_tools.py"],
        },
    ),
    oxy.ChatAgent(
        name="planner_agent",
        desc="An agent capable of making plans",
        llm_model="default_llm",
        prompt="""
            For a given goal, create a simple and step-by-step executable plan. \
            The plan should be concise, with each step being an independent and complete functional module—not an atomic function—to avoid over-fragmentation. \
            The plan should consist of independent tasks that, if executed correctly, will lead to the correct answer. \
            Ensure that each step is actionable and includes all necessary information for execution. \
            The result of the final step should be the final answer. Make sure each step contains all the information required for its execution. \
            Do not add any redundant steps, and do not skip any necessary steps.
        """.strip(),
    ),
    oxy.ReActAgent(
        name="executor_agent",
        desc="An agent capable of executing tools",
        sub_agents=[
            "time_agent",
            "time_agent_b",
            "time_agent_c",
            "file_agent",
            "math_agent",
        ],
        tools=["joke_tool"],
        llm_model="default_llm",
        timeout=100,
        prompt="""
                    You are a helpful assistant who can use the following tools:
                    ${tools_description}

                    You only need to complete the **current step** in the plan—do not do anything extra.
                    Respond strictly according to the requirements of the current step.
                    If a tool is required, select one from the tools listed above. Do not choose any other tool.
                    If multiple tool calls are needed, call only **one** tool at a time. You will receive the result and continue after that.
                    If no tool is needed, respond directly—**do not output anything else**.

                    Important Instructions:
                    1. When you have collected enough information to answer the user's question, respond using the following format:
                    <think>Your reasoning (if necessary)</think>
                    Your actual response

                    2. When the user's question lacks necessary information, you may ask a clarification question. Use the format:
                    <think>Your reasoning (if necessary)</think>
                    Your clarification question

                    3. When you need to use a tool, you must respond with the following **exact** JSON object format, and **nothing else**:
                    ```json
                    {
                        "think": "Your reasoning (if necessary)",
                        "tool_name": "Tool name",
                        "arguments": {
                            "parameter_name": "parameter_value"
                        }
                    }
                    ```

                    After receiving the tool's response:
                    1. Convert the raw data into a natural conversational reply
                    2. Be concise but informative
                    3. Focus on the most relevant information
                    4. Use appropriate context from the user's question
                    5. Avoid simply repeating the raw data

                    Only use the explicitly defined tools above. If no tool is needed, reply directly—**do not output anything else**.
            """,
    ),
    oxy.PlanAndSolve(
        name="master_agent",
        is_discard_react_memory=True,
        llm_model="default_llm",
        is_master=True,
        planner_agent_name="planner_agent",
        executor_agent_name="executor_agent",
        enable_replanner=False,
        timeout=100,
    ),
    oxy.ReActAgent(
        name="time_agent",
        desc="A tool for querying the time",
        tools=["time"],
        llm_model="default_llm",
        timeout=100,
    ),
    oxy.ReActAgent(
        name="time_agent_b",
        desc="A tool for querying the time",
        tools=["time"],
        llm_model="default_llm",
        timeout=100,
    ),
    oxy.ReActAgent(
        name="time_agent_c",
        desc="A tool for querying the time",
        tools=["time"],
        llm_model="default_llm",
        timeout=100,
    ),
    oxy.ReActAgent(
        name="file_agent",
        desc="A tool for operating the file system",
        tools=["filesystem"],
        llm_model="default_llm",
    ),
    oxy.WorkflowAgent(
        name="math_agent",
        desc="A tool for querying the value of pi",
        sub_agents=["time_agent"],
        tools=["my_tools"],
        func_workflow=workflow,
        llm_model="default_llm",
        is_retain_master_short_memory=True,
    ),
]


async def main():
    mas = await MAS.create(oxy_space=oxy_space)
    queries = [
        # Query 1
        "What time is it now? Please save it to the file log.txt under the local_file folder.",
        # Query 2: Write a Chinese food review
        "What time is it now?",
        "Please help me write a review for a food delivery. "
        "I had a barbecue street stall, and the dishes I ordered included grilled lamb skewers, grilled tenderloin, grilled buns, and grilled eggplant. "
        "The average cost per person was under 100 RMB. Please praise the server for being super enthusiastic. "
        "Use Chinese, and keep it under 100 characters.",
        # Query 3: Generate Hive SQL to check row count in a table
        "Please write Hive SQL code to query the number of rows in the 7Fresh order table. "
        "The table is gdm.gdm_7fresh_order_info. "
        "All fields are of type string. The field details are: "
        "dt is the partition field, order_id is the order ID, order_status is the order status, "
        "order_time is the order time, order_amount is the order amount, "
        "order_type is the order type, order_source is the order source, "
        "order_remark is the order remark, order_remark_type is the remark type, "
        "order_remark_content is the remark content, order_remark_time is the remark time, "
        "order_remark_user is the user who made the remark, order_remark_user_id is their ID, "
        "order_remark_user_name is their name, order_remark_user_phone is their phone number.",
    ]
    await mas.start_web_service(first_query=queries[0])


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
