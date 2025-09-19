import pytest

from oxygent.preset_tools.python_tools import run_python_code


@pytest.mark.asyncio
async def test_simple_code_execution():
    code = "result = 2 + 3"
    output = await run_python_code(code, variable_to_return="result")
    assert output == "5"
    code = "x = 10"
    output = await run_python_code(code)
    assert output == "successfully run python code"
    code = "x = 5"
    output = await run_python_code(code, variable_to_return="y")
    assert output == "Variable y not found"


@pytest.mark.asyncio
async def test_error_handling():
    code = "raise ValueError('Test error')"
    output = await run_python_code(code)
    assert "Error running python code" in output
    assert "Test error" in output


@pytest.mark.asyncio
async def test_with_others():
    code = "result = test_var * 2"
    custom_globals = {"test_var": 10}
    output = await run_python_code(
        code, variable_to_return="result",
        safe_globals=custom_globals)
    assert output == "20"
    code = "message = 'Hello World'"
    output = await run_python_code(code, variable_to_return="message")

    assert output == "Hello World"
    code = "numbers = [1, 2, 3, 4, 5]"
    output = await run_python_code(code, variable_to_return="numbers")
    assert output == "[1, 2, 3, 4, 5]"

    code = "flag = True"
    output = await run_python_code(code, variable_to_return="flag")
    assert output == "True"
