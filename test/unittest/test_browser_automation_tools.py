"""
Unit tests for browser automation tools
"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from oxygent.preset_tools.browser_automation_tools import (
    browser_automation_tools,
    navigate_to_url,
    extract_page_content,
    take_screenshot,
    get_page_links,
    fill_form,
    _get_browser_context
)
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_browser_context():
    """Mock browser context for testing."""
    context = AsyncMock()
    page = AsyncMock()
    
    # Configure page mock
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value="Test Page Title")
    page.url = "https://example.com"
    page.text_content = AsyncMock(return_value="Test page content")
    page.screenshot = AsyncMock()
    page.close = AsyncMock()
    page.evaluate = AsyncMock(return_value=[
        {"text": "Link 1", "href": "https://example.com/link1", "title": ""},
        {"text": "Link 2", "href": "https://example.com/link2", "title": "Title 2"}
    ])
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    
    # Configure context mock
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    
    return context, page


@pytest.fixture
def sample_oxy_request():
    """Sample OxyRequest for testing."""
    return OxyRequest(
        arguments={},
        caller="test_agent",
        caller_category="agent",
        current_trace_id="test_trace_123"
    )


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_navigate_to_url_success(mock_browser_context):
    """Test successful URL navigation."""
    context_mock, page_mock = mock_browser_context
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await navigate_to_url("https://example.com")
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "success"
    assert result_data["title"] == "Test Page Title"
    assert result_data["url"] == "https://example.com"
    assert "Successfully navigated" in result_data["message"]
    
    # Verify mock calls
    page_mock.goto.assert_called_once_with(
        "https://example.com", 
        wait_until="domcontentloaded", 
        timeout=30000
    )
    page_mock.title.assert_called_once()
    page_mock.close.assert_called_once()


@pytest.mark.asyncio
async def test_navigate_to_url_error(mock_browser_context):
    """Test URL navigation with error."""
    context_mock, page_mock = mock_browser_context
    page_mock.goto.side_effect = Exception("Navigation failed")
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await navigate_to_url("https://invalid-url.com")
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "error"
    assert result_data["url"] == "https://invalid-url.com"
    assert "Navigation failed" in result_data["error"]
    assert "Failed to navigate" in result_data["message"]


@pytest.mark.asyncio
async def test_extract_page_content_success(mock_browser_context):
    """Test successful content extraction."""
    context_mock, page_mock = mock_browser_context
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await extract_page_content(
            "https://example.com", 
            selector="body", 
            max_length=1000
        )
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "success"
    assert result_data["url"] == "https://example.com"
    assert result_data["selector"] == "body"
    assert result_data["content"] == "Test page content"
    assert result_data["length"] == len("Test page content")
    
    # Verify mock calls
    page_mock.goto.assert_called_once()
    page_mock.text_content.assert_called_once_with("body")
    page_mock.close.assert_called_once()


@pytest.mark.asyncio
async def test_extract_page_content_no_content(mock_browser_context):
    """Test content extraction when no content is found."""
    context_mock, page_mock = mock_browser_context
    page_mock.text_content.return_value = None
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await extract_page_content("https://example.com", selector=".nonexistent")
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "warning"
    assert result_data["content"] == ""
    assert "No content found" in result_data["message"]


@pytest.mark.asyncio
async def test_take_screenshot_success(mock_browser_context):
    """Test successful screenshot capture."""
    context_mock, page_mock = mock_browser_context
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await take_screenshot(
            "https://example.com", 
            output_path="test_screenshot.png",
            full_page=True
        )
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "success"
    assert result_data["url"] == "https://example.com"
    assert "test_screenshot.png" in result_data["screenshot_path"]
    assert result_data["full_page"] is True
    assert "Screenshot saved" in result_data["message"]
    
    # Verify mock calls
    page_mock.goto.assert_called_once()
    page_mock.screenshot.assert_called_once()
    page_mock.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_page_links_success(mock_browser_context):
    """Test successful link extraction."""
    context_mock, page_mock = mock_browser_context
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await get_page_links(
            "https://example.com",
            filter_domain=True,
            max_links=10
        )
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "success"
    assert result_data["url"] == "https://example.com"
    assert result_data["total_links"] == 2
    assert result_data["filter_domain"] is True
    assert len(result_data["links"]) == 2
    assert result_data["links"][0]["text"] == "Link 1"
    assert result_data["links"][0]["href"] == "https://example.com/link1"
    
    # Verify mock calls
    page_mock.goto.assert_called_once()
    page_mock.evaluate.assert_called_once()
    page_mock.close.assert_called_once()


@pytest.mark.asyncio
async def test_fill_form_success(mock_browser_context):
    """Test successful form filling."""
    context_mock, page_mock = mock_browser_context
    
    form_data = json.dumps({
        "input[name='username']": "testuser",
        "input[name='email']": "test@example.com"
    })
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await fill_form(
            "https://example.com/form",
            form_data=form_data,
            submit=False
        )
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "success"
    assert result_data["url"] == "https://example.com/form"
    assert result_data["submitted"] is False
    assert len(result_data["filled_fields"]) == 2
    assert result_data["filled_fields"][0]["status"] == "success"
    assert "Form filled successfully" in result_data["message"]
    
    # Verify mock calls
    page_mock.goto.assert_called_once()
    assert page_mock.fill.call_count == 2
    page_mock.close.assert_called_once()


@pytest.mark.asyncio
async def test_fill_form_with_submit(mock_browser_context):
    """Test form filling with submission."""
    context_mock, page_mock = mock_browser_context
    
    form_data = json.dumps({"input[name='username']": "testuser"})
    
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context', 
               return_value=context_mock):
        result = await fill_form(
            "https://example.com/form",
            form_data=form_data,
            submit=True,
            submit_selector="button[type='submit']"
        )
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "success"
    assert result_data["submitted"] is True
    assert "Form filled and submitted" in result_data["message"]
    
    # Verify mock calls
    page_mock.fill.assert_called_once()
    page_mock.click.assert_called_once_with("button[type='submit']")
    page_mock.wait_for_load_state.assert_called_once()


@pytest.mark.asyncio
async def test_fill_form_invalid_json():
    """Test form filling with invalid JSON data."""
    with patch('oxygent.preset_tools.browser_automation_tools._get_browser_context'):
        result = await fill_form(
            "https://example.com/form",
            form_data="invalid json",
            submit=False
        )
    
    # Parse result
    result_data = json.loads(result)
    
    # Assertions
    assert result_data["status"] == "error"
    assert "form_data must be valid JSON" in result_data["error"]


def test_browser_tools_registration():
    """Test that browser tools are properly registered in the FunctionHub."""
    # Check that the FunctionHub instance exists
    assert browser_automation_tools.name == "browser_automation_tools"
    
    # Check that tools are registered
    expected_tools = [
        "navigate_to_url",
        "extract_page_content", 
        "take_screenshot",
        "get_page_links",
        "fill_form"
    ]
    
    for tool_name in expected_tools:
        assert tool_name in browser_automation_tools.func_dict
        tool_desc, tool_func = browser_automation_tools.func_dict[tool_name]
        assert isinstance(tool_desc, str)
        assert callable(tool_func)


@pytest.mark.asyncio
async def test_get_browser_context_import_error():
    """Test browser context initialization with missing Playwright."""
    global _browser_context
    original_context = _browser_context
    _browser_context = None
    
    try:
        with patch('oxygent.preset_tools.browser_automation_tools.async_playwright') as mock_playwright:
            mock_playwright.side_effect = ImportError("Playwright not found")
            
            with pytest.raises(ImportError, match="Playwright not installed"):
                await _get_browser_context()
    finally:
        _browser_context = original_context
