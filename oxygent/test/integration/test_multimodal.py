import pytest
import re

from examples.advanced.multimodal_demo import main as multimodal_test

# Skip the test if multimodal demo is not available

@pytest.mark.asyncio
async def test_multimodal_demo(capfd):
    await multimodal_test()

    captured = capfd.readouterr()
    output = captured.out.strip()

    assert output, "No output found"

    assert re.search(r"True|true", output), "Output does not contain expected result"