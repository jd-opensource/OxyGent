# Oxy Message Class

## OxyState

| Parameter                            | Type / Allowed value                                                                         | Default | Description                                      |
| ------------------------------------ | -------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------ |
| *No dataclass fields; enum members:* | Allowed values: `CREATED`, `RUNNING`, `COMPLETED`, `FAILED`, `PAUSED`, `SKIPPED`, `CANCELED` | —       | Lifecycle states used to label a node’s status.  |


## OxyRequest (Pydantic BaseModel)

### Parameters

| Parameter                  | Type / Allowed value         | Default                        | Description                                 |
| -------------------------- | ---------------------------- | ------------------------------ | ------------------------------------------- |
| `request_id`               | `str`                        | auto-generated (ShortUUID, 22) | Client-side id used for tracing/resume.     |
| `group_id`                 | `str`                        | auto-generated (ShortUUID, 16) | Static identifier to group related traces.  |
| `from_trace_id`            | `Optional[str]`              | `""`                           | Parent node’s trace id.                     |
| `current_trace_id`         | `Optional[str]`              | auto-generated (ShortUUID, 16) | Unique id for this node.                    |
| `reference_trace_id`       | `Optional[str]`              | `""`                           | Reference pointer for special flows.        |
| `restart_node_id`          | `Optional[str]`              | `""`                           | Node id to restart from.                    |
| `restart_node_output`      | `Optional[str]`              | `""`                           | Cached output for restart.                  |
| `restart_node_order`       | `Optional[str]`              | `""`                           | Order index for restart.                    |
| `is_load_data_for_restart` | `bool`                       | `True`                         | Whether to reload data from DB.             |
| `input_md5`                | `Optional[str]`              | `""`                           | Hash of the input payload.                  |
| `root_trace_ids`           | `list`                       | `[]`                           | All root ids of the session tree.           |
| `mas`                      | `Optional[Any]`              | `None`                         | Handle to the MAS runtime (not dumped).     |
| `caller`                   | `Optional[str]`              | `"user"`                       | Name of the caller oxy.                     |
| `callee`                   | `Optional[str]`              | `""`                           | Name of the callee oxy.                     |
| `call_stack`               | `List[str]`                  | `["user"]`                     | Stack of caller names.                      |
| `node_id_stack`            | `List[str]`                  | `[""]`                         | Stack of node ids.                          |
| `father_node_id`           | `Optional[str]`              | `""`                           | Parent node id.                             |
| `pre_node_ids`             | `Optional[List[str] \| str]` | `[]`                           | Predecessor node ids.                       |
| `latest_node_ids`          | `Optional[List[str] \| str]` | `[]`                           | Latest parallel node ids.                   |
| `caller_category`          | `Optional[str]`              | `"user"`                       | Category of caller (user/agent/tool).       |
| `callee_category`          | `Optional[str]`              | `""`                           | Category of callee.                         |
| `node_id`                  | `Optional[str]`              | `""`                           | Current node id.                            |
| `arguments`                | `dict`                       | `{}`                           | Call arguments (user inputs, tool args).    |
| `is_save_history`          | `bool`                       | `True`                         | Whether to persist conversation history.    |
| `shared_data`              | `dict`                       | `{}`                           | Scratchpad shared within the trace.         |
| `parallel_id`              | `Optional[str]`              | `""`                           | Parallel group identifier.                  |
| `parallel_dict`            | `Optional[dict]`             | `{}`                           | Internal map for parallel scheduling.       |

### Methods

| Method                                                     | Coroutine （async） | Return Value  | Purpose (concise)                                                                                       |
| ---------------------------------------------------------- | ----------------- | ------------- | ------------------------------------------------------------------------------------------------------- |
| `session_name` (property)                                  | No                | `str`         | Convenient session key: `"caller__callee"`.                                                             |
| `set_mas(self, mas)`                                       | No                | `None`        | Attach MAS runtime handle.                                                                              |
| `get_oxy(self, oxy_name)`                                  | No                | `Any`         | Look up an oxy by name in MAS registry.                                                                 |
| `has_oxy(self, oxy_name)`                                  | No                | `bool`        | Check if an oxy exists in MAS registry.                                                                 |
| `__deepcopy__(self, memo)`                                 | No                | `OxyRequest`  | Custom deep copy preserving MAS/shared\_data and resetting parallel info.                               |
| `clone_with(self, **kwargs)`                               | No                | `OxyRequest`  | Deep-copy then override selected fields atomically.                                                     |
| `retry_execute(self, oxy, oxy_request=None)`               | Yes               | `OxyResponse` | Execute with retries and backoff using `oxy.retries`/`oxy.delay`.                                       |
| `call(self, **kwargs)`                                     | Yes               | `OxyResponse` | Clone with overrides, permission-check, timeout-guard, special-cases `retrieve_tools`, then execute.    |
| `start(self)`                                              | Yes               | `OxyResponse` | Entry: run the target callee’s `execute` with this request.                                             |
| `send_message(self, message)`                              | Yes               | `None`        | Push a structured event to the frontend via MAS/Redis.                                                  |
| `set_query(self, query, master_level=False)`               | No                | `None`        | Store query either at master (`shared_data`) or node (`arguments`) level.                               |
| `get_query(self, master_level=False)`                      | No                | `str`         | Fetch query from master or node scope.                                                                  |
| `get_full_parts(self, master_level=False)`                 | No                | `list`        | Return query in A2A-style ordered parts (list of `{part: {...}}`).                                      |
| `has_short_memory(self, master_level=False)`               | No                | `bool`        | Whether short-term memory exists at chosen scope.                                                       |
| `set_short_memory(self, short_memory, master_level=False)` | No                | `None`        | Set short-term memory at chosen scope.                                                                  |
| `get_short_memory(self, master_level=False)`               | No                | `list`        | Get short-term memory at chosen scope.                                                                  |
| `get_request_id(self)`                                     | No                | `str`         | Return the current `request_id`.                                                                        |
| `set_request_id(self, request_id)`                         | No                | `None`        | Manually override `request_id`.                                                                         |
| `get_group_id(self)`                                       | No                | `str`         | Return the `group_id`.                                                                                  |
| `set_group_id(self, request_id)`                           | No                | `None`        | Manually override `group_id`.                                                                           |

## OxyResponse (Pydantic BaseModel)

### Parameters

| Parameter     | Type / Allowed value   | Default          | Description                                  |
| ------------- | ---------------------- | ---------------- | -------------------------------------------- |
| `state`       | `OxyState`             | must be assigned | Final state of the task.                     |
| `output`      | `Any`                  | must be assigned | User-visible payload or error message.       |
| `extra`       | `dict`                 | `{}`             | Optional metadata (e.g., tokens, latency).   |
| `oxy_request` | `Optional[OxyRequest]` | `None`           | Echo of the originating request.             |

### Methods

| Method          | Coroutine （async） | Return Value | Purpose (concise)                                           |
| --------------- | ----------------- | ------------ | ----------------------------------------------------------- |
| *None declared* | —                 | —            | Data container model; relies on Pydantic-generated methods. |

## OxyOutput (Pydantic BaseModel)


### Parameters

| Parameter     | Type / Allowed value | Default          | Description                      |
| ------------- | -------------------- | ---------------- | -------------------------------- |
| `result`      | `Any`                | must be assigned | Primary result payload.          |
| `attachments` | `list`               | `[]`             | List of attachment descriptors.  |

