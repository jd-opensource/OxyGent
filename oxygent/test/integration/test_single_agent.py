# tests/integration/test_single_demo.py

import re

import pytest

from examples.agents.single_demo import main


@pytest.mark.asyncio
async def test_single_demo_integration(capfd):
    """Integration test for single_demo.

    This test runs the single_demo main function and verifies that the output
    contains a reasonable assistant response, without hardcoding exact LLM outputs.
    """

    # Run the main function in single_demo
    await main()

    # Capture stdout
    captured = capfd.readouterr()
    output = captured.out.strip()

    # Basic assertions:
    # 1. Output is not empty.
    assert output, "Output should not be empty"

    # 2. Output is a string and reasonably long (avoid one-word degenerate outputs).
    assert isinstance(output, str)
    assert len(output) > 5, "Output should be a meaningful assistant response"

    # 3. Check general patterns without enforcing exact content.
    expected_patterns = [
        r".*assist.*",
        r".*help.*",
        r".*hello.*",
    ]
    assert any(re.search(pat, output, re.IGNORECASE) for pat in expected_patterns), (
        "Output does not match expected assistant-like patterns. "
        f"Actual output: {output}"
    )
