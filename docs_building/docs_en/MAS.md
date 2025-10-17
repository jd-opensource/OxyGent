# 1 Introduction

This module is the core module of the OxyGent framework's Multi-Agent System (MAS), implementing the overall management and operational logic of the MAS. Its main content and responsibilities include:

- **MAS System Core Class:** Defines the MAS class, responsible for the lifecycle management of the entire multi-agent platform, including initialization, startup, shutdown, resource recycling, etc.;
- **Agent and Tool Registration Management:** Supports registration, batch registration, and dynamic management of Agents and Tools, with unified management achieved through name mapping;
- **Organizational Structure Construction:** Automatically build and display the organizational structure tree of agents and their subordinate tools, facilitating visualization and logical hierarchical management;
- **Database and Resource Management:** Integrate various database clients including Elasticsearch, Redis, Vearch, etc., to implement data storage, retrieval, and message flow, automatically creating required indexes and table structures;
- **Task and Session Management:** Maintains active tasks, asynchronous operations, message queues, etc., supports batch processing and concurrent execution, and adapts to various interaction modes such as SSE, CLI, and Web API;
- **Web Services and API Interfaces:** Based on the FastAPI framework, providing RESTful and SSE asynchronous interfaces, supporting web frontend integration, organizational structure queries, welcome messages and initial conversations;
- **Running auxiliary functions:** including welcome message display, Banner startup, dynamic attribute settings, Agent invocation and message pushing, etc., to implement a flexible and scalable multi-agent collaboration mechanism.

# 2 Initialization

## 2.1 Required Parameter

No parameter.

## 2.2 Return Value

No return Value.

## 2.3 Execution Process

![Intinalization Process.png](../images/Intinalization%20Process.png)

### 2.3.1 Oxy Agent Registration

1. Batch inject the default Oxy space into the system (equivalent to performing a "resource declaration") to prepare for subsequent instance initialization;
2. If it is detected that the Vearch configuration is enabled, an additional retrieval capability entity will be registered (for subsequent integration of vector retrieval functions). This is done before instance initialization to ensure that it can be discovered during subsequent loading.

### 2.3.2 Initialize the Database Cnnection

1. Establish a connection with Elasticsearch for log, retrieval, or structured data storage and querying; 
2. Establish a connection with Redis for scenarios such as caching, queuing, rate limiting, or sessions; 
3. When the Vearch configuration is enabled, prepare for table/index creation related to vector retrieval in subsequent steps (closely associated with the database phase).

### 2.3.3 Initialize the Oxy Instance

1. Iterate through all registered Oxy items, build their instances one by one, execute their initialization hooks (if any), and complete dependency injection; 
2. Ensure that the instantiation order complies with the dependency topology (if some Oxys depend on other Oxys or underlying services, their pre-initialization is guaranteed in the second step).

### 2.3.4 Initialize the Master Agent Name

1. Parse the master agent name from the configuration or default rules. If not explicitly configured, use the agreed default name；
2. Inject the master agent name into the context of MAS as key metadata for routing, display, and organizational structure construction.

### 2.3.5 Initialize the Agent Organization

1. Generate a hierarchical or graph-like organizational structure based on the ready Oxy instances and the master agent name；
2. Establish a "directory" of relationships and division of responsibilities between agents to provide a structured basis for task orchestration and message routing;
3. Finally, print or display the organizational structure as a visual confirmation of successful startup.

# 3 Interact with the agent

In MAS, interaction with the agent is mainly conducted through the `chat_with_agent` function.

## 3.1 Required Parameter

|     Name     | Type | Default Value |                     Description                     |
|:------------:|:----:|:-------------:|:---------------------------------------------------:|
|   payload    | dict |     None      | Information required for interacting with the agent |
| send_msg_key | str  |      ""       |                  Redis storage key                  |

## 3.2 Return Value

|  **Class**  |  **Description**   |
| :---------: | :----------------: |
| OxyResponse | Oxy Response Class |

## 3.3 Execution Process

![chat_with_agent interact process.png](../images/chat_with_agent%20interact%20process.png)

### 3.3.1 Intialize Shared Data

1. If there is no `shared_data` in the payload, initialize an empty dictionary;
2. Store the user query `payload["query"]` in `shared_data` to ensure this core information is accessible in subsequent processes.

### 3.3.2 Handle Node Restart Logic (if `restart_node_id` is specified)

When the payload contains `restart_node_id`, query the historical data of the node through Elasticsearch (ES):

1. If node data is found, check whether `reference_trace_id` (reference trace ID) matches the node's `trace_id`:

    - If matched, record the node's update time (`restart_node_order`) for session recovery;
    - If not matched, record a warning log.

2. If `reference_trace_id` is not specified, automatically set the node's `trace_id` as the reference ID and record the update time;

3. If no node data is found, record a warning log.

### 3.3.3 Construct `OxyRequest` Object

1. Initialize `OxyRequest` (the system's internal request object) and associate it with the current MAS instance;

2. Extract `group_data` (group data) from the payload and assign it to the request object;

3. If the payload contains `current_trace_id` (current trace ID), set it in the request object for session tracking.

### 3.3.4 Inherit Historical Session Data (if `from_trace_id` is specified)

When the payload contains `from_trace_id`, query the historical session corresponding to this trace ID through ES:

1. If historical data is found, extract `group_id`(group ID) and `group_data`(historical group data):
    - If the historical `group_data` is a string, attempt to parse it into a dictionary; use an empty dictionary if parsing fails;
    - Merge the historical `group_data` with the current `group_data` and update it to the request object to ensure session context continuity.
2. If no historical data is found, record a warning log.

### 3.3.5 Populate Request Parameters

Iterate through key-value pairs in the payload and map them to the OxyRequest object:

1. If the key is an inherent field of OxyRequest (e.g., `callee`, `trace_id`), directly set it as an object property;
2. Otherwise, store it in the `arguments` dictionary of the request object (as input parameters for the agent).

### 3.3.6 Determine Target Agent

If the request object does not specify `callee` (target agent name), use the system's master agent (`master_agent_name`) by default.

### 3.3.7 Execute Request and Return Result

1. Call `oxy_request.start()` to execute the request asynchronously and obtain the agent's response `oxy_response`;
2. If `send_msg_key` is specified, send an end event (`{"event": "close", "data": "done"}`) to Redis to notify the SSE client that the session has ended;
3. Return the complete `OxyResponse` object.

# 4 Interact with users

Three ways of interacting with users are defined in MAS: command-line interaction, web page interaction, and batch processing interaction.

## 4.1 MAS.start_cli_mode

### 4.1.1 Required Parameters

|  **Name**   | **Type** | **Default Value** |     **Description**      |
| :---------: | :------: | :---------------: | :----------------------: |
| first_query |  string  |       None        | The question to be asked |

### 4.1.2 Return Value

No return value.

### 4.1.3 Execution Process

1. Initialize `trace_id` as empty. If it is the first question (i.e., no context exists), proceed to Step 2; otherwise, proceed to Step 3;
2. Pass the `query` and `trace_id` to the `MAS.chat_with_agent` function, obtain the answer, print the answer, and then proceed to Step 3;
3. Judge the input:
    - If the input is ("exit", "quit", "bye"), exit the mode;
    - If the input is ("reset", "clear"), clear the context (i.e., set`trace_id`to empty);
    - If it is a normal question, proceed to Step 2.

### 4.1.4 Usage Example

```python
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_cli_mode(
            first_query="Hello!"
        )
```

## 4.2 MAS.start_web_service

### 4.2.1 Interface Design

|        **Name**        | **Schema** |    **Request Parameters**    |                          **返回值**                          |                           **说明**                           |
| :--------------------: | :--------: | :--------------------------: | :----------------------------------------------------------: | :----------------------------------------------------------: |
|  `/get_organization`   |    GET     |              -               | `{  "id_dict": { "agent_name1": 0, "agent_name2": 1, ... },  "organization": { ... }  // 智能体组织结构树，含 path 字段 } ` | Returns agent/tool organization structure (includes path field in organization tree) |
|   `/get_first_query`   |    GET     |              -               |            `{  "first_query": "首次对话内容" } `             |            Returns the first conversation content            |
| `/get_welcome_message` |    GET     |              -               |          `{  "welcome_message": "欢迎消息内容" } `           |                   Returns welcome message                    |
|        `/chat`         |  GET/POST  | querypayloadcurrent_trace_id |                          output:any                          | Regular asynchronous conversation, supports request interception and agent responses |
|      `/sse/chat`       |  GET/POST  | querypayloadcurrent_trace_id |              `{ "data": "模型输出/事件内容" } `              | SSE event stream for real-time message push in asynchronous tasks. Sends `{ "event": "close", "data": "done" }` at the end. |
|     `/async/chat`      |  GET/POST  | querypayloadcurrent_trace_id |                            `{} `                             | Asynchronous conversation interface, returns only empty WebResponse object, actual processing occurs asynchronously in the background. |

### 4.2.2 Execution Process

1. **Parameter and Configuration Initialization:**
    - Process incoming parameters: first_query, welcome_message, host, port;
    - Default configurations are taken from Config;
    - Log warning if main agent is not registered.
2. **FastAPI Application and Middleware Initialization:**
    - Create FastAPI instance;
    - Add CORS middleware;
    - Mount custom middleware and routes;
    - Mount web frontend resource directory `/web` and static upload directory `/static` to ensure page and file access.
3. **Unified Request Handling:**
    - `request_to_payload()` is responsible for GET/POST parsing, JSON conversion, and completing query, trace_id, headers, etc.;
    - Adapts for subsequent method calls.
4. **Service Startup and Automatic Web Page Opening:**
    - Asynchronously start Uvicorn service;
    - Automatically open frontend page (if configuration allows);
    - Record relevant logs.

### 4.2.3 Usage Example

```python
import asyncio

from oxygent import MAS, oxy
from oxygent.utils.env_utils import get_env_var

master_prompt = """
你是一个文档分析专家，用户会向你提供文档，请为用户提供简要的文档摘要。
摘要可以是markdown格式。
"""

oxy_space = [
    oxy.HttpLLM(
        name="default_llm",
        api_key=get_env_var("DEFAULT_LLM_API_KEY"),
        base_url=get_env_var("DEFAULT_LLM_BASE_URL"),
        model_name=get_env_var("DEFAULT_LLM_MODEL_NAME"),
        llm_params={"temperature": 0.01},
        semaphore=4,
        timeout=240,
    ),
    oxy.ReActAgent(
        name="master_agent",
        prompt = master_prompt,
        is_master=True,
        llm_model="default_llm",
    ),
]


async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        await mas.start_web_service(
            first_query="Hello!"
        )


if __name__ == "__main__":
    asyncio.run(main())
```

## 4.3 MAS.start_batch_processing()

### 4.3.1 Required Parameters

|    **Name**     | **Type** | **Default Value** |            **Description**             |
| :-------------: | :------: | :---------------: | :------------------------------------: |
|     querys      |   list   |         -         |             Question list              |
| return_trace_id |   bool   |       False       | Control whether to return the trace ID |

### 4.3.2 Return Value

| **Name** | **Type** | **Default Value** | **Description** |
| :------: | :------: | :---------------: | :-------------: |
| results  |   list   |         -         |   Answer list   |

### 4.3.3 Execution Process

1. Create an asynchronous task for each query. For each task, perform these steps:
    - Set `trace_id` to `""`;
    - Pass the `query` and `trace_id` to the `MAS.chat_with_agent` function, with `"extra_arg"` set to `"value"`;
    - Obtain and return the answer for this query.
2. Wait for all queries to be processed, then return all outputs.

### 4.3.4 Usage Example

```python
async def main():
    async with MAS(oxy_space=oxy_space) as mas:
        outs = await mas.start_batch_processing(["Hello!"] * 10, return_trace_id=True)
        print(outs)
```

