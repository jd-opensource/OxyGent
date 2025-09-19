import os
import pytest
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

from oxygent.preset_tools.shell_tools import run_shell_command


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_success(mock_run):
    """Test successful shell command execution"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "line1\nline2\nline3\nline4\nline5"
    mock_run.return_value = mock_result

    result = await run_shell_command(["echo", "test"])

    mock_run.assert_called_once_with(
        ["echo", "test"],
        capture_output=True,
        encoding="utf8",
        shell=True,
        text=True,
        cwd=None
    )
    assert result == "line1\nline2\nline3\nline4\nline5"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_with_tail(mock_run):
    """Test shell command execution with custom tail value"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "line1\nline2\nline3\nline4\nline5\nline6"
    mock_run.return_value = mock_result

    result = await run_shell_command(["echo", "test"], tail=3)

    assert result == "line4\nline5\nline6"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_with_base_dir(mock_run):
    """Test shell command execution with custom base directory"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "success"
    mock_run.return_value = mock_result

    test_dir = "/tmp/test"
    result = await run_shell_command(["pwd"], base_dir=test_dir)

    mock_run.assert_called_once_with(
        ["pwd"],
        capture_output=True,
        encoding="utf8",
        shell=True,
        text=True,
        cwd=test_dir
    )
    assert result == "success"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_error(mock_run):
    """Test shell command execution with error"""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Command not found"
    mock_run.return_value = mock_result

    result = await run_shell_command(["nonexistent_command"])

    assert result == "Error: Command not found"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_exception(mock_run):
    """Test shell command execution with exception"""
    mock_run.side_effect = Exception("Subprocess failed")

    result = await run_shell_command(["test"])

    assert result == "Error: Subprocess failed"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_empty_output(mock_run):
    """Test shell command execution with empty output"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_run.return_value = mock_result

    result = await run_shell_command(["echo", "-n", ""])

    assert result == ""


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_single_line(mock_run):
    """Test shell command execution with single line output"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "single line"
    mock_run.return_value = mock_result

    result = await run_shell_command(["echo", "single line"])

    assert result == "single line"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_large_tail(mock_run):
    """Test shell command execution with tail larger than output lines"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "line1\nline2"
    mock_run.return_value = mock_result

    result = await run_shell_command(["echo", "test"], tail=10)

    assert result == "line1\nline2"


@pytest.mark.asyncio
@patch('subprocess.run')
async def test_run_shell_command_zero_tail(mock_run):
    """Test shell command execution with zero tail"""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "line1\nline2\nline3"
    mock_run.return_value = mock_result

    result = await run_shell_command(["echo", "test"], tail=0)

    assert result == "line1\nline2\nline3"
