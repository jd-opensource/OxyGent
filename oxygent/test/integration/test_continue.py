# tests/integration/test_continue_exec_demo.py

import re

import pytest

from examples.advanced.continue_exec_demo import main


@pytest.mark.asyncio
async def test_continue_exec_demo_integration(capfd):
    """Integration test for continue_exec_demo.

    This test runs the continue_exec_demo main function and verifies that
    the output contains valid assistant response with expected structural fields.
    """

    # Run the demo main
    await main()

    # Capture stdout
    captured = capfd.readouterr()
    output = captured.out.strip()

    # Basic assertions:
    assert output, "Output should not be empty"

    # Extract lines containing 'time' but not error-like phrases
    matched_lines = []
    for line in output.splitlines():
        if re.search(r"time", line, re.IGNORECASE):
            if not re.search(r"sorry|error|exception", line, re.IGNORECASE):
                matched_lines.append(line)

    # Check that at least one valid time-related line is present
    assert matched_lines, "No valid time-related output found"

    # Further validate that each matched line is meaningful
    for line in matched_lines:
        assert len(line) > 10, f"Line too short: {line}"
        # Optionally check for typical timezone or time words
        assert re.search(
            r"time|timezone|datetime|hour|min|second", line, re.IGNORECASE
        ), f"Line does not appear to contain time info: {line}"
