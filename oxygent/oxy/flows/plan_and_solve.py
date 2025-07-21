import logging
from typing import Callable, List, Optional, Union

from pydantic import BaseModel, Field

from ...schemas import LLMResponse, Message, OxyRequest, OxyResponse, OxyState
from ...utils.llm_pydantic_parser import PydanticOutputParser
from ..base_flow import BaseFlow

logger = logging.getLogger(__name__)


class Plan(BaseModel):
    """Plan to follow in future."""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )


class Response(BaseModel):
    """Response to user."""

    response: str


class Action(BaseModel):
    """Action to perform."""

    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )


class PlanAndSolve(BaseFlow):
    """Plan-and-Solve Prompting Workflow."""

    max_replan_rounds: int = Field(30, description="Maximum retries for operations.")

    planner_agent_name: str = Field("planner_agent", description="planner agent name")
    pre_plan_steps: List[str] = Field(None, description="pre plan steps")

    enable_replanner: bool = Field(False, description="enable replanner")

    executor_agent_name: str = Field(
        "executor_agent", description="executor agent name"
    )

    llm_model: str = Field("default_llm", description="LLM model name for fallback")

    func_parse_planner_response: Optional[Callable[[str], LLMResponse]] = Field(
        None, exclude=True, description="planner response parser"
    )

    pydantic_parser_planner: PydanticOutputParser = Field(
        default_factory=lambda: PydanticOutputParser(output_cls=Plan),
        description="planner pydantic parser",
    )

    func_parse_replanner_response: Optional[Callable[[str], LLMResponse]] = Field(
        None, exclude=True, description="replanner response parser"
    )

    pydantic_parser_replanner: PydanticOutputParser = Field(
        default_factory=lambda: PydanticOutputParser(output_cls=Action),
        description="replanner pydantic parser",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add_permitted_tools(
            [
                self.planner_agent_name,
                self.executor_agent_name,
            ]
        )

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        plan_str = ""
        past_steps = ""
        original_query = oxy_request.get_query()
        plan_steps = self.pre_plan_steps
        for current_round in range(self.max_replan_rounds + 1):
            if (current_round == 0) and (self.pre_plan_steps is None):
                if self.pydantic_parser_planner:
                    query = self.pydantic_parser_planner.format(original_query)
                else:
                    query = original_query.copy()

                oxy_response = await oxy_request.call(
                    callee=self.planner_agent_name,
                    arguments={"query": query},
                )
                if self.pydantic_parser_planner:
                    plan_response = self.pydantic_parser_planner.parse(
                        oxy_response.output
                    )
                else:
                    plan_response = self.func_parse_planner_response(
                        oxy_response.output
                    )
                plan_steps = plan_response.steps
                plan_str = "\n".join(
                    f"{i + 1}. {step}" for i, step in enumerate(plan_steps)
                )

            task = plan_steps[0]
            task = plan_steps[0]
            task_formatted = f"""
                We have finished the following steps: {past_steps}
                The current step to execute is:{task}
                You should only execute the current step, and do not execute other steps in our plan. Do not execute more than one step continuously or skip any step.
            """.strip()
            excutor_response = await oxy_request.call(
                callee=self.executor_agent_name,
                arguments={"query": task_formatted},
            )
            past_steps = (
                past_steps
                + "\n"
                + f"task:{task}, execute task result:{excutor_response.output}"
            )
            if self.enable_replanner:
                # Replanning logic
                query = """
                The target of user is:
                {input}

                The origin plan is:
                {plan}

                We have finished the following steps:
                {past_steps}

                Please update the plan considering the mentioned information. If no more operation is supposed, Use **Response** to answer the user. 
                Otherwise, please update the plan. The plan should only contain the steps to be executed, and do not 
                include the past steps or any other information.
                """.format(input=original_query, plan=plan_str, past_steps=past_steps)
                if self.pydantic_parser_replanner:
                    query = self.pydantic_parser_replanner.format(query)

                replanner_response = await oxy_request.call(
                    callee=self.replanner_agent_name,
                    arguments={
                        "query": query,
                    },
                )
                if self.pydantic_parser_replanner:
                    plan_response = self.pydantic_parser_replanner.parse(
                        replanner_response.output
                    )
                else:
                    plan_response = self.func_parse_planner_response(
                        replanner_response.output
                    )

                if hasattr(plan_response.action, "response"):
                    return OxyResponse(
                        state=OxyState.COMPLETED,
                        output=plan_response.action.response,
                    )
                else:
                    plan_response = plan_response.action
                    plan_steps = plan_response.steps
                    plan_str = "\n".join(
                        f"{i + 1}. {step}" for i, step in enumerate(plan_steps)
                    )
            else:
                plan_steps = plan_steps[1:]

                if 0 == len(plan_steps):
                    return OxyResponse(
                        state=OxyState.COMPLETED,
                        output=excutor_response.output,
                    )

        plan_steps = plan_response.steps
        plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan_steps))
        user_input_with_results = f"Your objective was this：{oxy_request.get_query()}\n---\nFor the following plan：{plan_str}"
        temp_messages = [
            Message.system_message(
                "Please answer user questions based on the given plan."
            ),
            Message.user_message(user_input_with_results),
        ]
        oxy_response = await oxy_request.call(
            callee=self.llm_model,
            arguments={"messages": [msg.to_dict() for msg in temp_messages]},
        )
        return OxyResponse(
            state=OxyState.COMPLETED,
            output=oxy_response.response,
        )
