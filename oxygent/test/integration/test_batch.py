"""
    Befor using integration tests, make sure to check the following steps:
        + The llms, vlms, api keys and other required environment variables are set.
        + The models are available and accessible.
        + The source data is available and accessible.
        + The SSE network is available and accessible.
    Even if we pass the above checks, we still do not guarantee that the synthetic tests will pass 100% of the time for the correct code: 
    for some specific models, it is really difficult to predict the output of those models, so we only set up some very simple fuzzy matches. 
    For developers who need to check the quality of their code, we strongly recommend running unit tests first, 
    and if you have better suggestions for testing, you are welcome to make a pull request.
"""
import pytest
import re
import ast

from examples.agents.batch_demo import main


@pytest.mark.asyncio
async def test_batch_demo_integration(capfd):
    await main()
    captured = capfd.readouterr()
    output = captured.out.strip()
    assert output, "Output should not be empty"

    matches = re.findall(r"(\[.*\])", output, re.DOTALL)
    assert matches, "No list-like output found"

    outs = ast.literal_eval(matches[-1])

    assert isinstance(outs, list)
    assert len(outs) == 10

    for entry in outs:
        assert isinstance(entry, dict)
        assert "output" in entry and "trace_id" in entry
        assert isinstance(entry["output"], str) and len(entry["output"]) > 5

