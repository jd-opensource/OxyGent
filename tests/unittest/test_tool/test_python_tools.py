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
async def test_captures_stdout():
    output = await run_python_code("print('first')\nprint('second')")
    assert output == "first\nsecond"


@pytest.mark.asyncio
async def test_captures_stderr():
    output = await run_python_code("import sys\nprint('warning', file=sys.stderr)")
    assert output == "[stderr] warning"


@pytest.mark.asyncio
async def test_returns_stdout_and_variable():
    output = await run_python_code(
        "print('calculated')\nresult = 42", variable_to_return="result"
    )
    assert output == "calculated\n42"


@pytest.mark.asyncio
async def test_preserves_empty_execution_namespaces():
    safe_globals = {}
    safe_locals = {}
    output = await run_python_code(
        "result = 42",
        variable_to_return="result",
        safe_globals=safe_globals,
        safe_locals=safe_locals,
    )
    assert output == "42"
    assert safe_locals["result"] == 42


@pytest.mark.asyncio
async def test_with_others():
    code = "result = test_var * 2"
    custom_globals = {"test_var": 10}
    output = await run_python_code(
        code, variable_to_return="result", safe_globals=custom_globals
    )
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
