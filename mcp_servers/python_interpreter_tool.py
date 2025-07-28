import os,sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append('..')

from mcp.server.fastmcp import FastMCP
from pydantic import Field
from mcp_servers.local_python_executor import (
    BASE_PYTHON_TOOLS,
    evaluate_python_code,
)

mcp = FastMCP('a2', port=9001)


from oxygent import oxy
pi = oxy.FunctionHub(name="python_interpreter_tool", timeout=900)


@pi.tool(description="This is a tool that evaluates python code. It can be used to perform calculations.")
def python_interpreter_api(
    code: str = Field(description="The python code to run in interpreter.")
) -> str:
    try:
        state = {}
        output = str(
            evaluate_python_code(
                code,
                state=state,
                static_tools=BASE_PYTHON_TOOLS,
            )[0]  # The second element is boolean is_final_answer
        )

        output = f"Stdout:\n{str(state['_print_outputs'])}\nOutput: {output}"

    except Exception as e:
        return f"Error: {e}"
    return output


if __name__ == '__main__':
    print('running')
