# tests/integration/test_parallel_demo.py

import re

import pytest

from examples.agents.parallel_demo import test as parallel_demo_test


@pytest.mark.asyncio
async def test_parallel_demo_integration(capfd):
    """Integration test for parallel_demo.

    Verifies that:
    - Output contains comprehensive summary keywords
    - Output contains detailed structured content and a summary section
    - Each expert agent's section is present
    - No generic apology or fallback response is included
    """

    # Run the demo test function
    await parallel_demo_test()

    # Capture stdout
    captured = capfd.readouterr()
    output = captured.out.strip()

    # Debug print (optional)
    # print("Captured output:", output)

    assert output, "Output should not be empty"

    # Extract the LLM output
    match = re.search(r"LLM:\s*(.+)", output, re.DOTALL)
    assert match, "No LLM output line found"

    result = match.group(1)

    # 1. Check for comprehensive summary keywords
    summary_keywords = ["comprehensive", "summary", "parallel"]
    assert any(kw in result.lower() for kw in summary_keywords), (
        "Output lacks required summary keywords"
    )

    # 2. Check format contains structured content (e.g. numbered or markdown sections)
    structured_patterns = [r"1\.", r"###", r"####", r"\*\*"]
    assert any(re.search(pat, result) for pat in structured_patterns), (
        "Output lacks structured detailed content"
    )

    # 3. Check all expert agent sections are included
    expert_keywords = ["technical", "business", "risk", "legal"]
    for expert in expert_keywords:
        assert re.search(expert, result, re.IGNORECASE), (
            f"Output missing {expert} section"
        )

    # 4. Ensure no 'sorry', 'error', or apology-like fallback statements
    forbidden_patterns = [r"sorry", r"error", r"apolog"]
    for pat in forbidden_patterns:
        assert not re.search(pat, result, re.IGNORECASE), (
            f"Output contains forbidden pattern: {pat}"
        )
