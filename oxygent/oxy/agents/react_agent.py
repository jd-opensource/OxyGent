"""ReAct agent module for reasoning and acting capabilities.

This module provides the ReActAgent class, which implements the ReAct (Reasoning and
Acting) paradigm for autonomous agent behavior. It combines language model reasoning
with tool execution in an iterative loop.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

from pydantic import Field

from ...config import Config
from ...prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_RETRIEVAL
from ...schemas import (
    ExecResult,
    LLMResponse,
    LLMState,
    Memory,
    Message,
    Observation,
    OxyRequest,
    OxyResponse,
    OxyState,
)
from ...utils.common_utils import chunk_list, extract_first_json, generate_uuid
from .local_agent import LocalAgent

logger = logging.getLogger(__name__)


class ReActAgent(LocalAgent):
    """Agent implementing the ReAct (Reasoning and Acting) paradigm.

    This agent creates autonomous behavior by combining language model reasoning
    with tool execution in an iterative loop. It supports various tool retrieval
    modes and memory management strategies for optimal performance.

    Tool Retrieval Modes:
        Default: Passive tool retrieval based on current query regardless of tool count.

        Mode 1 - No Retrieval: Return all available tools
            top_k_tools = float('inf')
            is_retrieve_even_if_tools_scarce = False

        Mode 2 - Query-based Retrieval: Automatically retrieve N tools based on query
            top_k_tools = N

        Mode 3 - Active Sourcing: Provide sourcing tool for agent-driven retrieval
            is_sourcing_tools = True
            top_k_tools = N

    Attributes:
        max_react_rounds (int): Maximum number of reasoning-acting iterations.
        is_discard_react_memory (bool): Whether to discard detailed ReAct memory.
        memory_max_tokens (int): Maximum tokens for memory management.
        trust_mode (bool): Whether to enable trust mode for direct tool results.

    TODO:
        - LLM model: Support both service URLs and weight files for training
        - Agent long memory: Vector-based HTTP URL addition
    """

    max_react_rounds: int = Field(16, description="Maximum retries for operations.")

    is_discard_react_memory: bool = Field(
        True, description="Whether to discard react_memory"
    )
    func_map_memory_order: Callable[[int], int] = Field(
        lambda x: x, exclude=True, description="Function to map order to score"
    )
    memory_max_tokens: int = Field(
        24800, description="Maximum tokens supported by memory"
    )
    weight_short_memory: int = Field(5, description="Weight for short_memory")
    weight_react_memory: int = Field(1, description="Weight for react_memory")

    trust_mode: bool = Field(False, description="Enable trust mode for direct results")

    func_parse_llm_response: Optional[Callable[[str, OxyRequest], LLMResponse]] = Field(
        None, exclude=True, description="Function to parse LLM output"
    )

    func_reflexion: Optional[Callable[[str, OxyRequest], str]] = Field(
        None, exclude=True, description="Function to perform reflexion on responses"
    )

    def __init__(self, **kwargs):
        """Initialize the ReAct agent with appropriate prompt and parsing function."""
        super().__init__(**kwargs)

        if not self.prompt:
            self.prompt = (
                SYSTEM_PROMPT_RETRIEVAL if self.is_sourcing_tools else SYSTEM_PROMPT
            )
        if self.func_parse_llm_response is None:
            self.func_parse_llm_response = self._parse_llm_response

        if self.func_reflexion is None:
            self.func_reflexion = self._default_reflexion

        # Add retrieve_tools if vector search is conf igured
        if Config.get_vearch_config():
            self.tools.append("retrieve_tools")

    def _default_reflexion(self, response: str, oxy_request: OxyRequest) -> str:
        """Default reflexion function that checks if response is empty or invalid.

        Args:
            response (str): The agent's response to evaluate
            oxy_request (OxyRequest): The current request context

        Returns:
            reflection_message (str): Feedback message for improvement (used when is_acceptable=False)
        """
        # Check if response is empty
        if not response or len(response.strip()) == 0:
            return "The response should not be empty. Please provide a more detailed and helpful answer."
        return None

    async def _get_history(
        self, oxy_request: OxyRequest, is_get_user_master_session=False
    ) -> Memory:
        """Retrieve conversation history with intelligent memory management.

        This method implements sophisticated memory management that can either
        discard detailed ReAct memory for simplicity or retain it with weighted
        scoring for optimal context preservation.

        Args:
            oxy_request (OxyRequest): The current request containing trace information.
            is_get_user_master_session (bool): Whether to retrieve master session
                history by joining the first two elements of call_stack.

        Returns:
            Memory: Processed conversation history optimized for context.
        """
        short_memory = Memory()
        if is_get_user_master_session:
            session_name = "__".join(oxy_request.call_stack[:2])
        else:
            session_name = oxy_request.session_name
        es_response = await self.mas.es_client.search(
            Config.get_app_name() + "_history",
            {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "terms": {
                                    "trace_id": oxy_request.root_trace_ids
                                    + [oxy_request.current_trace_id]
                                }
                            },
                            {"term": {"session_name": session_name}},
                        ]
                    }
                },
                "size": self.short_memory_size,
                "sort": [{"create_time": {"order": "desc"}}],
            },
        )
        historys = es_response["hits"]["hits"][::-1]
        if self.is_discard_react_memory:
            # Simple mode: Only keep query-answer pairs
            for history in historys:
                memory = json.loads(history["_source"]["memory"])
                short_memory.add_message(Message.user_message(memory["query"]))
                short_memory.add_message(Message.assistant_message(memory["answer"]))
        else:
            # Advanced mode: Weighted memory management with token limits
            # Collect all question-answer pairs from both short and ReAct memory
            qa_list = []
            for short_i, history in enumerate(historys):
                memory = json.loads(history["_source"]["memory"])
                qa_list.append((memory["query"], memory["answer"], short_i, "short"))
                for react_q, react_a in chunk_list(memory["react_memory"]):
                    qa_list.append(
                        (react_q["content"], react_a["content"], short_i, "react")
                    )

            # Calculate weighted scores for each QA pair
            scores = []
            for i, (q, a, short_i, memory_type) in enumerate(qa_list):
                weight = (
                    self.weight_short_memory
                    if memory_type == "short"
                    else self.weight_react_memory
                )
                scores.append(self.func_map_memory_order(i + 1) * weight)

            # Sort indices by score (highest first) for priority selection
            sorted_scores = [
                index
                for index, _ in sorted(
                    enumerate(scores), key=lambda x: x[1], reverse=True
                )
            ]

            # Apply token-based filtering to stay within limits
            count_token = 0
            retained_index = set()
            for index in sorted_scores:
                q, a, short_i, memory_type = qa_list[index]
                count_token += len(q)
                count_token += len(a)
                if count_token > self.memory_max_tokens:
                    break
                retained_index.add(index)

            # Reconstruct memory maintaining conversation flow
            short_a_message = None
            for i, (q, a, short_i, memory_type) in enumerate(qa_list):
                if i not in retained_index:
                    continue
                if memory_type == "short":
                    if short_a_message:
                        short_memory.add_message(
                            Message.assistant_message(short_a_message)
                        )
                        short_a_message = None
                    short_memory.add_message(Message.user_message(q))
                    short_a_message = a
                else:
                    if short_a_message is None:
                        continue
                    short_memory.add_message(Message.assistant_message(q))
                    short_memory.add_message(Message.user_message(a))
            if short_a_message:
                short_memory.add_message(Message.assistant_message(short_a_message))
        return short_memory

    def _parse_llm_response(
        self, ori_response: str, oxy_request: OxyRequest = None
    ) -> LLMResponse:
        """Parse LLM response to determine next action.

        This method handles various LLM output formats and determines whether
        the response is a tool call, final answer, or parsing error.

        Args:
            ori_response (str): Raw LLM response text.

        Returns:
            LLMResponse: Parsed response with state and extracted content.
        """
        try:
            # Handle think model format
            if "</think>" in ori_response:
                ori_response = ori_response.split("</think>")[-1].strip()
            # Extract JSON code segment
            tool_call_dict = json.loads(extract_first_json(ori_response))

            if "tool_name" in tool_call_dict:
                return LLMResponse(
                    state=LLMState.TOOL_CALL,
                    output=tool_call_dict,
                    ori_response=ori_response,
                )
            else:
                return LLMResponse(
                    state=LLMState.ERROR_PARSE,
                    output="Please answer strictly according to the format. If you want to call a tool, provide tool_name.",
                    ori_response=ori_response,
                )

        except json.JSONDecodeError:
            if all([tk in ori_response for tk in ["tool_name", "arguments", "{", "}"]]):
                return LLMResponse(
                    state=LLMState.ERROR_PARSE,
                    output="JSON cannot be parsed properly, please provide the answer again.",
                    ori_response=ori_response,
                )
            else:
                reflection_msg = self.func_reflexion(ori_response, oxy_request)
                if reflection_msg:
                    return LLMResponse(
                        state=LLMState.ERROR_PARSE,
                        output=reflection_msg,
                        ori_response=ori_response,
                    )
                return LLMResponse(
                    state=LLMState.ANSWER,
                    output=ori_response,
                    ori_response=ori_response,
                )
        except Exception as e:
            logger.warning(e)
            return LLMResponse(
                state=LLMState.ERROR_PARSE, output=e, ori_response=ori_response
            )

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the ReAct reasoning and acting loop.

        This method implements the core ReAct algorithm by iterating between
        reasoning (LLM calls) and acting (tool execution) until a satisfactory
        answer is found or maximum rounds are reached.

        Args:
            oxy_request (OxyRequest): The request to process.

        Returns:
            OxyResponse: Final response with answer and ReAct memory trace.
        """
        react_memory = Memory()
        for current_round in range(self.max_react_rounds + 1):
            # Build complete message context: instruction + short memory + query + react memory
            temp_memory = Memory()
            temp_memory.add_message(
                Message.system_message(self._build_instruction(oxy_request.arguments))
            )
            temp_memory.add_messages(
                Message.dict_list_to_messages(oxy_request.get_short_memory())
            )
            # Add current query and ReAct history
            temp_memory.add_message(Message.user_message(oxy_request.get_query()))
            temp_memory.add_messages(react_memory.messages)

            full_memory = temp_memory.to_dict_list()
            oxy_response = await oxy_request.call(
                callee=self.llm_model,
                arguments={"messages": full_memory},
            )
            oxy_request.arguments["full_memory"] = full_memory
            llm_response = self.func_parse_llm_response(
                oxy_response.output, oxy_request
            )

            # Execute based on LLM decision
            if llm_response.state is LLMState.ANSWER:
                return OxyResponse(
                    state=OxyState.COMPLETED,
                    output=llm_response.output,
                    extra={"react_memory": react_memory.to_dict_list()},
                )
            elif llm_response.state is LLMState.TOOL_CALL:
                # Execute tool calls (possibly multiple)
                if isinstance(llm_response.output, dict):
                    tool_call_dict_list = [llm_response.output]
                elif isinstance(llm_response.output, list):
                    tool_call_dict_list = llm_response.output
                else:
                    raise ValueError(
                        f"Invalid tool call output type: {type(llm_response.output)}"
                    )

                parallel_id = generate_uuid()
                oxy_responses = await asyncio.gather(
                    *[
                        oxy_request.call(
                            callee=tool_call_dict["tool_name"],
                            arguments=tool_call_dict["arguments"],
                            parallel_id=parallel_id,
                        )
                        for tool_call_dict in tool_call_dict_list
                    ]
                )

                # observation_list = []
                observation = Observation()
                for tool_call_dict, oxy_response in zip(
                    tool_call_dict_list, oxy_responses
                ):
                    observation.add_exec_result(
                        ExecResult(
                            executor=tool_call_dict["tool_name"],
                            oxy_response=oxy_response,
                        )
                    )

                # When trust_mode == 1, write in short_memory，return observation
                if isinstance(llm_response.output, dict):
                    if self.trust_mode or (
                        "trust_mode" in llm_response.output
                        and llm_response.output["trust_mode"] == 1
                    ):
                        result_payload = observation.to_str()
                        return OxyResponse(
                            state=OxyState.COMPLETED,
                            output=result_payload,
                            extra={"react_memory": react_memory.to_dict_list()},
                        )

                # Add to ReAct memory for next iteration
                react_memory.add_message(
                    Message.assistant_message(llm_response.ori_response)
                )
                react_memory.add_message(Message.user_message(observation.to_str()))
            else:
                # Parsing error - add to memory for correction
                logger.info(
                    f"Format error, adding to react_memory: {llm_response.ori_response}",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )
                react_memory.add_message(
                    Message.assistant_message(llm_response.ori_response)
                )
                react_memory.add_message(Message.user_message(llm_response.output))

        # Fallback mechanism when max rounds reached
        # Extract tool call results for final summary
        tid = 1
        tool_call_results = []
        for message in react_memory.to_dict_list():
            if message["role"] != "user":
                continue
            tool_call_results.append(str(tid) + ". " + message["content"])
            tid += 1
        tool_call_results = "\n\n".join(tool_call_results)

        # Generate final answer based on accumulated results
        query = oxy_request.get_query()
        temp_messages = [
            Message.system_message(
                "Please answer the user's question based on the given tool execution results."
            ),
            Message.user_message(
                f"User question: {query}\n---\nTool execution results: {tool_call_results}"
            ),
        ]
        oxy_response = await oxy_request.call(
            callee=self.llm_model,
            arguments={"messages": [msg.to_dict() for msg in temp_messages]},
        )

        return OxyResponse(
            state=OxyState.COMPLETED,
            output=oxy_response.output,
            extra={"react_memory": react_memory.to_dict_list()},
        )
