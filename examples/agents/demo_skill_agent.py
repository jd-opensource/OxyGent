import asyncio
import argparse
import os
import sys


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from oxygent import MAS, oxy  # noqa: E402


def _build_default_llm():
    api_key = os.getenv("DEFAULT_LLM_API_KEY")
    base_url = os.getenv("DEFAULT_LLM_BASE_URL")
    model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")

    if base_url and model_name:
        return oxy.HttpLLM(
            name="default_llm",
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
        )

    async def _offline_response(oxy_request):
        messages = oxy_request.arguments.get("messages", [])
        query = ""
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                query = str(last.get("content", ""))

        system_text = ""
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, dict) and first.get("role") == "system":
                system_text = str(first.get("content", ""))

        skill_name = ""
        marker = "[SKILL ACTIVATED: "
        if marker in system_text:
            skill_name = system_text.split(marker, 1)[1].split("]", 1)[0].strip()

        if skill_name:
            return f"(offline demo) skill activated: {skill_name}\n\nYou said: {query}"
        return (
            "(offline demo) SkillAgent is running. "
            "Set DEFAULT_LLM_BASE_URL/DEFAULT_LLM_MODEL_NAME to enable selector.\n\n"
            f"You said: {query}"
        )

    return oxy.MockLLM(name="default_llm", func_mock_process=_offline_response)


async def main():
    parser = argparse.ArgumentParser(
        description="SkillAgent scoped skills demo (master + agent_a + agent_b)."
    )
    parser.add_argument(
        "--agent-a-skill-dir",
        required=True,
        help="Absolute directory path for agent_a skills.",
    )
    parser.add_argument(
        "--agent-b-skill-dir",
        required=True,
        help="Absolute directory path for agent_b skills.",
    )
    parser.add_argument("--web", action="store_true", help="Start web service mode.")
    args = parser.parse_args()

    def _ensure_abs_dir(path_value: str, arg_name: str) -> str:
        if not os.path.isabs(path_value):
            raise ValueError(f"{arg_name} must be an absolute path: {path_value}")
        if not os.path.isdir(path_value):
            raise ValueError(f"{arg_name} must be an existing directory: {path_value}")
        return os.path.realpath(path_value)

    agent_a_skill_dir = _ensure_abs_dir(args.agent_a_skill_dir, "--agent-a-skill-dir")
    agent_b_skill_dir = _ensure_abs_dir(args.agent_b_skill_dir, "--agent-b-skill-dir")

    base_url = os.getenv("DEFAULT_LLM_BASE_URL")
    model_name = os.getenv("DEFAULT_LLM_MODEL_NAME")
    selector_enabled = bool(base_url and model_name)

    oxy_space = [
        _build_default_llm(),
        oxy.ReActAgent(
            name="master_agent",
            llm_model="default_llm",
            sub_agents=["agent_a", "agent_b"],
            additional_prompt=(
                "Delegate skill-specific requests to agent_a or agent_b when appropriate. "
                "Use agent_a for scope A and agent_b for scope B."
            ),
        ),
        oxy.SkillAgent(
            name="agent_a",
            llm_model="default_llm",
            enable_selector=selector_enabled,
            skill_dirs=[agent_a_skill_dir],
            additional_prompt=(
                "Skills are NOT tools. Never use a skill name as tool_name. "
                "Only call tools that appear in tools_description. "
                "When a skill is activated, mention its name briefly before answering. "
                "You are agent_a and must only use skills from your configured scope."
            ),
        ),
        oxy.SkillAgent(
            name="agent_b",
            llm_model="default_llm",
            enable_selector=selector_enabled,
            skill_dirs=[agent_b_skill_dir],
            additional_prompt=(
                "Skills are NOT tools. Never use a skill name as tool_name. "
                "Only call tools that appear in tools_description. "
                "When a skill is activated, mention its name briefly before answering. "
                "You are agent_b and must only use skills from your configured scope."
            ),
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        print(f"\nagent_a skill dir: {agent_a_skill_dir}")
        print(f"agent_b skill dir: {agent_b_skill_dir}")

        for callee in ["agent_a", "agent_b"]:
            resp = await mas.chat_with_agent(
                payload={"callee": callee, "query": "list skills"}
            )
            print(f"\n[{callee}] discovered scoped skills:")
            print(resp.output)

        if args.web:
            first_query = (
                "Use prefix a: or b: in your query to indicate desired agent scope.\n"
                "Example: a: /skill-creator init hello-skill --path .oxygent/skills"
            )
            await mas.start_web_service(first_query=first_query)
            return

        print(
            "\nEnter queries below.\n"
            "Routing prefixes:\n"
            "- a: <query>  (send to agent_a)\n"
            "- b: <query>  (send to agent_b)\n"
            "- m: <query>  (send to master_agent)\n"
            "No prefix -> master_agent.\n"
            "\nExamples:\n"
            "- a: list skills\n"
            "- b: list skills\n"
            "- a: /skill-creator init hello-skill --path .oxygent/skills\n"
            "Type 'exit' to quit.\n"
        )

        trace_by_callee = {"master_agent": "", "agent_a": "", "agent_b": ""}
        while True:
            query = input("You: ").strip()
            if query in ["exit", "quit", "bye"]:
                break
            if not query:
                continue

            callee = "master_agent"
            actual_query = query
            if query.startswith("a:"):
                callee = "agent_a"
                actual_query = query[2:].strip()
            elif query.startswith("b:"):
                callee = "agent_b"
                actual_query = query[2:].strip()
            elif query.startswith("m:"):
                callee = "master_agent"
                actual_query = query[2:].strip()

            payload = {
                "query": actual_query,
                "callee": callee,
                "from_trace_id": trace_by_callee.get(callee, ""),
            }
            resp = await mas.chat_with_agent(payload=payload)
            trace_by_callee[callee] = resp.oxy_request.current_trace_id

            if resp.extra.get("skill_selection"):
                sel = resp.extra.get("skill_selection")
                print(f"[skill selection] {sel}")
            if resp.extra.get("skill_activation"):
                act = resp.extra.get("skill_activation")
                print(f"[skill activated] {act}")

            print(f"LLM({callee}):", resp.output)


if __name__ == "__main__":
    asyncio.run(main())
