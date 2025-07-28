import asyncio
import os
import json
import re
import logging
from typing import Dict, Any, List, Optional, Union

from oxygent import oxy, MAS, OxyRequest, OxyResponse
from oxygent.schemas.llm import LLMResponse, LLMState
from examples.gaia.gaia_prompt_v1 import (
    planning_agent_prompt_v1, browser_use_agent_prompt, deep_analyzer_agent_prompt,
    deep_researcher_agent_prompt, result_agent_prompt, master_agent_prompt_v1,
    code_agent_prompt, wayback_machine_agent_prompt, searcher_use_agent_prompt,
    wikipedia_research_agent_prompt, google_map_agent_prompt, youtube_research_agent_prompt,
    github_research_agent_prompt
)
from mcp_servers.deep_analyzer_tool import da
from mcp_servers.deep_research_tool import dr
from mcp_servers.python_interpreter_tool import pi
from mcp_servers.browser_use_tool import bs
from mcp_servers.get_url_from_wayback_machine import gwm
from mcp_servers.browser_simulator_tool import abs
from mcp_servers.excel2png_tool import ep
from mcp_servers.google_map_tool_async import google_map
from mcp_servers.google_map_url_tool import google_map_url
from mcp_servers.wiki_tool import wiki_tools
from mcp_servers.doc_qa_tool import doc_qa_tools
from mcp_servers.git_tool import github_tools
from mcp_servers.pdf_analyze_char_tool import analyze_pdf_character
from mcp_servers.youtube_tool import youtube_tools
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
env_path = Path('/examples/gaia/') / '.env'
load_dotenv(dotenv_path=env_path, verbose=True)

def insert_user_query(oxy_request: OxyRequest) -> OxyRequest:
    """Extracts the user query from the request and formats it for processing."""
    original_query = eval(oxy_request.get_query(master_level=True))
    oxy_request.arguments['query'] = original_query[-1]['text']
    if len(original_query) > 1:
        oxy_request.arguments['query'] += '\nFile_Name:' + original_query[0]['file_name']['file']
    return oxy_request


def extract_first_json(text: str) -> str:
    """Extracts the first JSON object found within triple-backtick JSON markers in the text."""
    json_matches = re.findall(r'```[\n]*json(.*?)```', text, re.DOTALL)
    json_texts = [match.strip() for match in json_matches]

    if json_texts:
        json_text = json_texts[0]
    else:
        json_text = text

    # Ensure the extracted text is a valid JSON object
    if not json_text.startswith('{') or not json_text.endswith('}'):
        json_text = json_text[json_text.find('{'): json_text.rfind('}') + 1]

    if len(json_texts) <= 1:
        json_text = text[text.find('{'): text.rfind('}') + 1]

    return json_text


def format_output(oxy_response: OxyResponse) -> OxyResponse:
    """Formats the response output as a JSON string."""
    oxy_response.output = json.dumps(oxy_response.output, ensure_ascii=False)
    return oxy_response


def parse_response(original_response: str) -> LLMResponse:
    """Parses the LLM response to determine if it's a tool call or a final answer."""
    try:
        # Extract JSON code segment
        try:
            tool_call_dict = json.loads(extract_first_json(original_response))
        except:
            tool_call_dict = eval(extract_first_json(original_response))

        if "tool_name" in tool_call_dict and tool_call_dict["tool_name"] not in ['final_answer']:
            # Handle tool call
            if "answer" in tool_call_dict["arguments"] and not isinstance(tool_call_dict["arguments"]["answer"], str):
                tool_call_dict["arguments"]["answer"] = json.dumps(tool_call_dict["arguments"]["answer"],
                                                                   ensure_ascii=False)
            if "query" in tool_call_dict["arguments"] and not isinstance(tool_call_dict["arguments"]["query"], str):
                tool_call_dict["arguments"]["query"] = json.dumps(tool_call_dict["arguments"]["query"],
                                                                  ensure_ascii=False)

            return LLMResponse(
                state=LLMState.TOOL_CALL,
                output=tool_call_dict,
                ori_response=original_response
            )
        elif tool_call_dict["tool_name"] in ['final_answer']:
            # Handle final answer
            if not isinstance(tool_call_dict["arguments"]["answer"], str):
                tool_call_dict["arguments"]["answer"] = json.dumps(tool_call_dict["arguments"]["answer"],
                                                                   ensure_ascii=False)

            return LLMResponse(
                state=LLMState.ANSWER,
                output=original_response,
                ori_response=tool_call_dict["arguments"]["answer"]
            )
        else:
            # Handle invalid format
            return LLMResponse(
                state=LLMState.ERROR_PARSE,
                output="Please answer strictly according to the format. If you want to call a tool, please provide tool_name.",
                ori_response=original_response
            )

    except json.JSONDecodeError:
        if all([tk in original_response for tk in ["tool_name", "arguments", "{", "}"]]) and not isinstance(
                tool_call_dict, dict):
            return LLMResponse(
                state=LLMState.ERROR_PARSE,
                output="JSON cannot be parsed correctly. Please provide a valid answer.",
                ori_response=original_response
            )
        else:
            if isinstance(tool_call_dict, dict) and len(tool_call_dict) > 0:
                original_response = tool_call_dict["arguments"]["answer"] if 'query' not in tool_call_dict["arguments"] \
                    else tool_call_dict["arguments"]["query"]

            if not isinstance(original_response, str):
                original_response = json.dumps(original_response, ensure_ascii=False)

            return LLMResponse(
                state=LLMState.ANSWER,
                output=original_response,
                ori_response=original_response
            )
    except Exception as e:
        logger.error(f"Error parsing response: {e}")
        return LLMResponse(
            state=LLMState.ERROR_PARSE,
            output=str(e),
            ori_response=original_response
        )


async def workflow(oxy_request: OxyRequest) -> Union[str, OxyResponse]:
    """Main workflow for processing user queries."""
    user_query = oxy_request.get_query()
    print(f'User query: {user_query}')

    # Get current time
    time_response = await oxy_request.call(
        callee='time_agent',
        arguments={"query": user_query}
    )
    print(f'Current time: {time_response.output}')

    # Check if the query contains a number for decimal precision
    numbers = re.findall(r'\d+', user_query)
    if numbers:
        precision = numbers[-1]
        pi_response = await oxy_request.call(
            callee='pi',
            arguments={"prec": precision}
        )
        return f'Value of pi to {precision} decimal places: {pi_response.output}'
    else:
        return 'Value of pi to 2 decimal places: 3.14. Alternatively, you can ask me to calculate pi to a specific number of decimal places.'


# Initialize the Oxygent workspace with all available tools and agents
oxy_workspace = [
    # Define LLM providers
    oxy.HttpLLM(
        name=os.getenv('DEEPSEEK_V3'),
        api_key=os.getenv('DEEPSEEK_KEY'),
        base_url=os.getenv('DEEPSEEK_URL') + '/chat/completions',
        model_name=os.getenv('DEEPSEEK_V3'),
        llm_params={'temperature': 0.01},
        semaphore=4,
        timeout=240
    ),
    oxy.HttpLLM(
        name=os.getenv('DEEPSEEK_R1'),
        api_key=os.getenv('DEEPSEEK_R1_KEY'),
        base_url=os.getenv('DEEPSEEK_R1_URL') + '/chat/completions',
        model_name=os.getenv('DEEPSEEK_R1'),
        llm_params={'temperature': 0.01},
        semaphore=4,
        timeout=240
    ),
    oxy.HttpLLM(
        name=os.getenv('GPT_4O'),
        api_key=os.getenv('OPEN_AI_KEY'),
        base_url=os.getenv('OPEN_AI_URL') + '/chat/completions',
        model_name=os.getenv('GPT_4O'),
        llm_params={'temperature': 0.01},
        semaphore=4,
        timeout=240
    ),
    oxy.HttpLLM(
        name=os.getenv('CLAUDE_SONNET'),
        api_key=os.getenv('CLAUDE_KEY'),
        base_url=os.getenv('CLAUDE_URL') + '/chat/completions',
        model_name=os.getenv('CLAUDE_SONNET'),
        llm_params={'temperature': 0.0},
        semaphore=4,
        timeout=240
    ),
    oxy.HttpLLM(
        name=os.getenv('CLAUDE_MODEL'),
        api_key=os.getenv('CLAUDE_KEY'),
        base_url=os.getenv('CLAUDE_URL') + '/chat/completions',
        model_name=os.getenv('CLAUDE_MODEL'),
        llm_params={'temperature': 0.01},
        semaphore=4,
        timeout=240
    ),

    # Register available tools
    da, dr, pi, bs, gwm, abs, ep,
    wiki_tools, google_map, google_map_url,
    doc_qa_tools, github_tools, analyze_pdf_character, youtube_tools,

    # Define ReAct agents for different tasks
    oxy.ReActAgent(
        name='deep_researcher_agent',
        desc='Conducts extensive web searches to solve complex web tasks.',
        tools=['deep_researcher_api', 'python_interpreter_api'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=deep_researcher_agent_prompt,
        func_parse_llm_response=parse_response,
    ),
    oxy.ReActAgent(
        name='browser_use_agent',
        desc='Solve simple single-page web task(search the [number/value/Noun] from the current single-web page.) Searches relevant web pages and interacts with them.',
        tools=['browser_use_api', 'python_interpreter_api'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=browser_use_agent_prompt,
        func_parse_llm_response=parse_response,
    ),
    oxy.ReActAgent(
        name='searcher_use_agent',
        desc='SEARCHER: Web page analysis & multi-task search. REQUIRES: research_question. FORBIDDEN: Code/game/URL-analysis.',
        sub_agents=['deep_researcher_agent', 'browser_use_agent', "wikipedia_research_agent"],
        tools=['async_advanced_browser_api'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=searcher_use_agent_prompt,
        func_parse_llm_response=parse_response,
    ),
    oxy.ReActAgent(
        name='deep_analyzer_agent',
        desc='ANALYZER: Processes files(CSV/JSON/DB), online data(PDF), code, games. REQUIRES: file_name/data_interface. PRIORITY: All gaming tasks.',
        tools=['deep_analyzer_api', 'python_interpreter_api', 'excel2png_api', "async_advanced_browser_api",
               "document_qa_tools", 'analyze_pdf_character_tool'],
        sub_agents=['code_agent', 'wikipedia_research_agent'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=deep_analyzer_agent_prompt,
        func_parse_llm_response=parse_response,
    ),
    oxy.ReActAgent(
        name='github_research_agent',
        desc='REPO ANALYST: Retrieves GitHub issue and pull request data. FEATURES: Milestone tracking, PR analytics, issue filtering. REQUIRES: Valid owner/repo GitHub identifier',
        tools=['github_apis'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=github_research_agent_prompt,
        func_parse_llm_response=parse_response,
        func_process_input=insert_user_query,
    ),
    oxy.ReActAgent(
        name='youtube_research_agent',
        desc='VIDEO RESEARCHER: Retrieves YouTube video metadata and transcripts. FEATURES: Multilingual captions, engagement analytics, timed text. REQUIRES: Valid YouTube video ID or extractable URL',
        tools=['youtube_apis'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=youtube_research_agent_prompt,
        func_parse_llm_response=parse_response,
        func_process_input=insert_user_query,
    ),
    oxy.ReActAgent(
        name='google_map_agent',
        desc='SEARCHER: This specialized agent performs automated historical exploration of Google Maps, generating direct-access URLs and executing time-based tasks including street view navigation, historical imagery analysis, and temporal verification of location features. REQUIRES: location and temporal task. FORBIDDEN: General web/code/timezone tasks.',
        tools=["google_map_tool", "google_map_url_tool"],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=google_map_agent_prompt,
        func_parse_llm_response=parse_response,
    ),
    oxy.ReActAgent(
        name='wayback_machine_agent',
        desc="ARCHIVER: Use ONLY when explicitly requesting historical URL snapshots.",
        tools=['get_wayback_machine_url_api'],
        sub_agents=['browser_use_agent'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=wayback_machine_agent_prompt,
        func_parse_llm_response=parse_response,
    ),
    oxy.ReActAgent(
        name='code_agent',
        desc='CODER: First-contact for programming/game/algorithm strategy tasks.',
        tools=['python_interpreter_api'],
        llm_model=os.getenv('CLAUDE_MODEL'),
        prompt=code_agent_prompt,
        func_parse_llm_response=parse_response,
        func_process_input=insert_user_query,
    ),
    oxy.ReActAgent(
        name='wikipedia_research_agent',
        desc='WIKI HISTORIAN: Provides Wikipedia content/revisions at specific dates. FEATURES: Edit counts, infobox values, revision comparisons. REQUIRES: Title that complies with Wikipedia format standards',
        tools=['wikipedia_tools'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=wikipedia_research_agent_prompt,
        func_parse_llm_response=parse_response,
        func_process_input=insert_user_query,
    ),
    oxy.ReActAgent(
        name='planning_agent',
        desc='**[First invoker]** Task decomposer using agent selection rules: 1. Data/file→🧠 2. Web→🔍 3. Code→⚙️ 4. HistoryURL→🕰️ 5. WikiHistory→📚 Gaming→🧠 | NoCodeInWeb🔍',
        sub_agents=['deep_analyzer_agent', 'searcher_use_agent', 'code_agent',
                    'result_agent', 'wayback_machine_agent', 'wikipedia_research_agent',
                    'google_map_agent', 'youtube_research_agent', 'github_research_agent'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=planning_agent_prompt_v1,
        func_parse_llm_response=parse_response,
        func_format_output=format_output,
        func_process_output=format_output,
    ),
    oxy.ReActAgent(
        name='result_agent',
        desc='FINISHER: Applies unit conversion(kg→tons), scaling(hundred→thousand) and formatting. INPUT: Must contain initial answer.',
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=result_agent_prompt,
        func_parse_llm_response=parse_response,
        func_format_output=format_output,
        func_process_output=format_output,
    ),
    oxy.ReActAgent(
        name='master_agent',
        is_master=True,
        desc='A planning agent that can plan the steps to complete the task.',
        sub_agents=['deep_analyzer_agent', 'searcher_use_agent', 'planning_agent', 'code_agent',
                    'result_agent', 'wayback_machine_agent', 'wikipedia_research_agent', 'google_map_agent',
                    'youtube_research_agent', 'github_research_agent'],
        llm_model=os.getenv('DEEPSEEK_V3'),
        prompt=master_agent_prompt_v1,
        func_parse_llm_response=parse_response,
        func_format_output=format_output,
        func_process_output=format_output,
        max_react_rounds=10
    )
]


async def main(query: Optional[List[Dict[str, Any]]] = None) -> str:
    """Main entry point for the application."""
    mas = await MAS.create(oxy_space=oxy_workspace)
    payload = {"query": str(query)}
    oxy_response = await mas.chat_with_agent(payload=payload)
    print(f"LLM Response: {oxy_response.output}")
    return oxy_response.output


if __name__ == "__main__":
    # Example query: Find the year when someone first edited the English Wikipedia page for horror movie character
    # Michael Myers on Halloween

    sample_query = [
        {"type": "text",
         "text": """As of August 2023, how many in-text citations on the West African Vodun Wikipedia page reference a 
         source that was cited using Scopus?"""}
    ]
    asyncio.run(main(sample_query))
