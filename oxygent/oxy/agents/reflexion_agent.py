import asyncio
import json
import logging
from typing import Callable, Optional

from pydantic import Field

from ...config import Config
from ...schemas import (
    LLMResponse,
    LLMState,
    Memory,
    Message,
    OxyRequest,
    OxyResponse,
    OxyState,
)
from ...utils.common_utils import chunk_list
from .react_agent import ReActAgent

logger = logging.getLogger(__name__)


class ReflexionAgent(ReActAgent):
    """Reflexion agent with dynamic memory and self-reflection capabilities.

    This agent combines Actor, Evaluator, and Self-Reflection modules to iteratively
    improve decisions, storing reflections into long-term memory to guide future behavior.

    Attributes:
        max_reflexion_rounds (int): Maximum retries for reflexion.
        weight_self_reflection_memory (int): Weight for self-reflection memory.
        evaluator_agent_name (str): Agent that evaluates decisions and produces rewards.
        evaluator_input_format (str): Input format for evaluator prompts.
        func_parse_evaluator_response (Callable): Function to parse evaluator output.
        self_reflection_agent_name (str): Agent that converts rewards into reflection text.
        self_reflection_input_format (str): Input format for self-reflection prompts.
        func_parse_self_reflection_response (Callable): Function to parse reflection output.
    """

    max_reflexion_rounds: int = Field(30, description="Maximum retries for operations.")
    weight_self_reflection_memory: int = Field(
        5, description="self_reflection_memory weights"
    )

    evaluator_agent_name: str = Field(
        None,
        description="Agent evaluating Actor decisions, outputting rewards or feedback."
        "Evaluation is a complex executation, thus we design Base Agent so that it could call different methods to evaluate",
    )

    evaluator_input_format: str = Field(None, description="Input format for evaluator.")

    func_parse_evaluator_response: Optional[Callable[[str], LLMResponse]] = Field(
        None, exclude=True, description="Input parser function of evaluator"
    )

    self_reflection_agent_name: str = Field(
        None,
        description="Agent converting rewards to reflection text as semantic gradient.",
    )

    self_reflection_input_format: str = Field(
        None, description="Input format for self-reflection agent."
    )

    func_parse_self_reflection_response: Optional[Callable[[str], LLMResponse]] = Field(
        None, exclude=True, description="Function to parse reflection output."
    )

    def __init__(
        self,
        func_parse_evaluator_response,
        func_parse_self_reflection_response,
        **kwargs,
    ):
        """Initializes ReflexionAgent with evaluator and reflection parsers."""
        super().__init__(**kwargs)
        self.func_parse_evaluator_response = func_parse_evaluator_response
        self.func_parse_self_reflection_response = func_parse_self_reflection_response

        self.extra_permitted_tool_name_list.extend(
            [self.evaluator_agent_name, self.self_reflection_agent_name]
        )

        if not self.evaluator_input_format:
            self.evaluator_input_format = """
                [Task]: {query}
                [Round {n_round} Answer]: {n_decision}
                [Round {n_round} Full Reasoning Process]: {n_reason}
                """.strip()

        if not self.self_reflection_input_format:
            self.self_reflection_input_format = """
                [Task]: {query}
                [Round {n_round} Answer]: {n_decision}
                [Round {n_round} Full Reasoning Process]: {n_reason}
                [Round {n_round} Evaluation Result]: {n_evaluation}
                """.strip()

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Executes reflexion process with actor, evaluator, and self-reflection.

        Args:
            oxy_request (OxyRequest): The incoming user request.

        Returns:
            OxyResponse: Final agent response.
        """
        # Reflexion memory, as well as long-term memory
        self_reflection_memory = Memory(max_messages=20)
        # Get origin query
        ori_user_query = oxy_request.get_query()
        # Start reflexion: no more than agent.max_react_rounds
        for current_round in range(self.max_reflexion_rounds + 1):
            # Use actor to solve
            oxy_response = await self.react_execute(
                oxy_request=oxy_request,
                self_refletion_memory=self_reflection_memory,
            )

            # Parser llm result
            llm_response = self.func_parse_llm_response(oxy_response.output)

            # evalutor
            # Join evaluator input
            if oxy_response.extra["react_memory"]:
                n_reason = "\n".join(
                    [
                        f"{msg['role']}: {msg['content']}"
                        for msg in oxy_response.extra["react_memory"]
                    ]
                )
            else:
                n_reason = "The assistant returned an answer directly without stepwise reasoning."
            evaluator_input = self.evaluator_input_format.format(
                query=ori_user_query,
                n_decision=llm_response.output,
                n_round=current_round,
                n_reason=n_reason,
            )
            # Call evaluator
            evaluate_oxy_reponse = await oxy_request.call(
                callee=self.evaluator_agent_name,
                arguments={"query": evaluator_input},
            )
            # Parser response
            evaluate_oxy_reponse = self.func_parse_evaluator_response(
                evaluate_oxy_reponse.output
            )
            # Return result if pass the evaluation, othervise
            if evaluate_oxy_reponse.state is LLMState.SUCCESS:
                return OxyResponse(
                    state=OxyState.COMPLETED,
                    output=llm_response.output,
                    extra={
                        "self_reflection_memory": self_reflection_memory.to_dict_list()
                    },
                )

            # self reflection
            self_reflection_input = self.self_reflection_input_format.format(
                query=ori_user_query,
                n_decision=llm_response.output,
                n_round=current_round,
                n_reason=n_reason,
                n_evaluation=str(evaluate_oxy_reponse.output),
            )
            self_relection_oxy_reponse = await oxy_request.call(
                callee=self.self_reflection_agent_name,
                arguments={"query": self_reflection_input},
            )
            # Parser results
            self_relection_oxy_reponse = self.func_parse_self_reflection_response(
                self_relection_oxy_reponse.output
            )
            # Write back the data after parser
            if self_relection_oxy_reponse.state is LLMState.SUCCESS:
                self_reflection_memory.add_message(
                    Message.user_message(str(evaluate_oxy_reponse.output))
                )
                self_reflection_memory.add_message(
                    Message.assistant_message(str(self_relection_oxy_reponse.output))
                )

        # Fallback mechanism: summarize reflections and answer
        # get_tool_call_results
        tid = 1
        self_reflection_results = []
        for message in self_reflection_memory.to_dict_list():
            if message["role"] != "user":
                continue
            self_reflection_results.append(str(tid) + ". " + message["content"])
            tid += 1
        tool_call_results = "\n\n".join(self_reflection_results)
        # Join messages to call llm
        user_input_with_results = f"User question: {oxy_request.get_query()}\n---\n Reflection contents:{tool_call_results}"
        temp_messages = [
            Message.system_message(
                "Please answer the user's question based on the reflections provided."
            ),
            Message.user_message(user_input_with_results),
        ]
        oxy_response = await oxy_request.call(
            callee=self.llm_model,
            arguments={"messages": [msg.to_dict() for msg in temp_messages]},
        )

        return OxyResponse(
            state=OxyState.COMPLETED,
            output=oxy_response.output,
            extra={"self_reflection_memory": self_reflection_memory.to_dict_list()},
        )

    async def react_execute(
        self,
        oxy_request: OxyRequest,
        self_refletion_memory: Memory,
    ) -> OxyResponse:
        """React execute the agent."""
        react_memory = Memory(max_messages=20)
        # Current be-called agent do ReAct, no more than agent.max_react_rounds
        for current_round in range(self.max_react_rounds + 1):
            # build messages
            # temp_memory = instruction（TODO: long mem embedding）+ short mem + query + react mem
            temp_memory = Memory(max_messages=40)
            temp_memory.add_message(
                Message.system_message(self._build_instruction(oxy_request.arguments))
            )
            # Read in short_memory
            temp_memory.add_messages(
                Message.dict_list_to_messages(oxy_request.get_short_memory())
            )
            # Read in self_refletion_memory
            temp_memory.add_messages(self_refletion_memory.messages)
            # Put in query
            temp_memory.add_message(Message.user_message(oxy_request.get_query()))
            # Read in react_memory
            temp_memory.add_messages(react_memory.messages)
            # llm call
            oxy_response = await oxy_request.call(
                callee=self.llm_model,
                arguments={"messages": temp_memory.to_dict_list()},
            )
            # Parser llm results
            llm_response = self.func_parse_llm_response(oxy_response.output)
            # Execute llm option
            if llm_response.state is LLMState.ANSWER:
                # Write back to short_memory
                return OxyResponse(
                    state=OxyState.COMPLETED,
                    output=llm_response.output,
                    extra={"react_memory": react_memory.to_dict_list()},
                )
            elif llm_response.state is LLMState.TOOL_CALL:
                if isinstance(llm_response.output, dict):
                    tool_call_dict_list = [llm_response.output]

                oxy_responses = await asyncio.gather(
                    *[
                        oxy_request.call(
                            callee=tool_call_dict["tool_name"],
                            arguments=tool_call_dict["arguments"],
                        )
                        for tool_call_dict in tool_call_dict_list
                    ]
                )

                observation_list = []
                for tool_call_dict, oxy_response in zip(
                    tool_call_dict_list, oxy_responses
                ):
                    if oxy_response.state is OxyState.COMPLETED:
                        tool_name = tool_call_dict["tool_name"]
                        observation_list.append(
                            f"Tool [{tool_name}] execution result: {oxy_response.output}"
                        )
                    else:
                        observation_list.append(oxy_response.output)
                observation = "\n\n".join(observation_list)
                # If trust_mode == 1, write back to short_memory，return observation
                if isinstance(llm_response.output, dict):
                    if (
                        self.trust_mode
                        and "trust_mode" in llm_response.output
                        and llm_response.output["trust_mode"] == 1
                    ):
                        # todo send_msg
                        return OxyResponse(
                            state=OxyState.COMPLETED,
                            output=observation,
                            extra={"react_memory": react_memory.to_dict_list()},
                        )
                react_memory.add_message(
                    Message.assistant_message(llm_response.ori_response)
                )
                react_memory.add_message(Message.user_message(observation))
            else:
                # Format error, write back to react_memory
                logger.info(
                    f"Error format, write to react_memory: {llm_response.ori_response}",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )
                react_memory.add_message(
                    Message.assistant_message(llm_response.ori_response)
                )
                react_memory.add_message(Message.user_message(llm_response.output))

        # Fallback mechanism
        # get_tool_call_results
        tid = 1
        tool_call_results = []
        for message in react_memory.to_dict_list():
            if message["role"] != "user":
                continue
            tool_call_results.append(str(tid) + ". " + message["content"])
            tid += 1
        tool_call_results = "\n\n".join(tool_call_results)
        user_input_with_results = f"User question: {oxy_request.get_query()}\n---\n Reflection contents:{tool_call_results}"
        temp_messages = [
            Message.system_message(
                "Please answer the user's question based on the reflections provided."
            ),
            Message.user_message(user_input_with_results),
        ]
        oxy_response = await oxy_request.call(
            callee=self.llm_model,
            arguments={"messages": [msg.to_dict() for msg in temp_messages]},
        )
        # Write back to short_memory
        return OxyResponse(
            state=OxyState.COMPLETED,
            output=oxy_response.output,
            extra={"react_memory": react_memory.to_dict_list()},
        )

    async def _get_history(
        self, oxy_request: OxyRequest, is_get_user_session=False
    ) -> Memory:
        short_memory = Memory()
        if oxy_request.from_trace_id:
            if is_get_user_session:
                session_name = "__".join(oxy_request.call_stack[:2])
            else:
                session_name = oxy_request.session_name
            es_response = await self.mas.es_client.search(
                Config.get_app_name() + "_history",
                {
                    "query": {
                        "bool": {
                            "must": [
                                {"terms": {"trace_id": oxy_request.root_trace_ids}},
                                {"term": {"session_name": session_name}},
                            ]
                        }
                    },
                    "size": self.short_memory_size,
                    "sort": [{"create_time": {"order": "desc"}}],
                },
            )
            historys = es_response["hits"]["hits"][::-1]
            # List qa pairs
            qa_list = []
            for short_i, history in enumerate(historys):
                memory = json.loads(history["_source"]["memory"])
                qa_list.append((memory["query"], memory["answer"], short_i, "short"))
                for react_q, react_a in chunk_list(memory["self_reflection_memory"]):
                    qa_list.append(
                        (
                            react_q["content"],
                            react_a["content"],
                            short_i,
                            "self_reflection",
                        )
                    )
            # Calculate the value of each qa
            scores = []
            for i, (q, a, short_i, memory_type) in enumerate(qa_list):
                weight = (
                    self.weight_short_memory
                    if memory_type == "short"
                    else self.weight_self_reflection_memory
                )
                scores.append(self.func_map_memory_order(i + 1) * weight)
            # Calculate sorted index
            sorted_scores = [
                index
                for index, _ in sorted(
                    enumerate(scores), key=lambda x: x[1], reverse=True
                )
            ]
            # Count token and filter qa
            count_token = 0
            retained_index = set()
            for index in sorted_scores:
                q, a, short_i, memory_type = qa_list[index]
                count_token += len(q)
                count_token += len(a)
                if count_token > self.memory_max_tokens:
                    break
                retained_index.add(index)
            # Filter special cases
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
