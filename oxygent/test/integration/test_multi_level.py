# tests/integration/test_multi_level_demo.py

import pytest
import re

from examples.advanced.multi_level_demo import test as multi_level_test


@pytest.mark.asyncio
async def test_multi_level_demo_integration(capfd):
    """Integration test for multi_level_demo.

    This test runs the multi_level_demo test function and verifies:
    - The output contains the correct pi digits prefix
    - No apology or error message is returned
    """

    # Run the demo test function
    await multi_level_test()

    # Capture stdout
    captured = capfd.readouterr()
    output = captured.out.strip()

    # Debug print (optional)
    # print("Captured output:", output)

    assert output, "Output should not be empty"

    # Extract the printed result line
    match = re.search(r"output:\s*(.+)", output)
    assert match, "No output line found"

    result = match.group(1)

    # 1. Check it starts with expected pi prefix
    expected_prefix = "The first 30"
    assert expected_prefix in result, f"Output does not contain expected prefix: {expected_prefix}"

    # Check for pi value pattern
    pi_pattern = r"3\.14159"
    assert re.search(pi_pattern, result), "Output does not contain valid pi value"

    # 2. Ensure no 'sorry', 'error', or apology-like words
    forbidden_patterns = [r"sorry", r"error", r"apolog"]
    for pat in forbidden_patterns:
        assert not re.search(pat, result, re.IGNORECASE), f"Output contains forbidden pattern: {pat}"
