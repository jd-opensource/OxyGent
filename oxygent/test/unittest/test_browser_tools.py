"""Test browser tools functionality."""

import os
import sys
import asyncio
from typing import Optional, AsyncGenerator
from unittest.mock import patch, MagicMock

# Add project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

try:
    import pytest
    import pytest_asyncio
    from playwright.async_api import Browser, BrowserContext, Page
except ImportError:
    print("请先安装必要的依赖：pip install pytest playwright pytest-asyncio")
    sys.exit(1)

from mcp_servers.browser_tools import (
    check_dependencies,
    _ensure_browser,
    _ensure_page,
    browser_navigate,
    browser_search,
    browser_click,
    browser_hover,
    browser_type,
    browser_snapshot,
    browser_take_screenshot,
    browser_tab_list,
    browser_tab_new,
    browser_tab_close,
    _close_browser
)

# 配置 pytest-asyncio 使用 auto 模式
pytest_plugins = ('pytest_asyncio',)

class TestBrowserTools:
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_browser(self) -> AsyncGenerator[None, None]:
        """Setup browser context for each test."""
        from mcp_servers.browser_tools import _browser, _context
        try:
            await _ensure_browser()
            yield
        finally:
            await _close_browser()

    def test_check_dependencies(self) -> None:
        """Test dependency checking functionality."""
        # Test case 1: playwright is installed
        with patch('importlib.import_module') as mock_import:
            mock_import.return_value = MagicMock()
            missing_deps = check_dependencies()
            assert len(missing_deps) == 0, "Should return empty list when playwright is installed"

        # Test case 2: playwright is not installed
        with patch('importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError()
            missing_deps = check_dependencies()
            assert 'playwright' in missing_deps, "Should return list containing playwright when not installed"

    @pytest.mark.asyncio
    async def test_ensure_browser(self) -> None:
        """Test browser initialization functionality."""
        try:
            from mcp_servers.browser_tools import _browser, _context
            assert _browser is not None, "Browser instance should be created"
            assert _context is not None, "Browser context should be created"
        except ImportError as e:
            pytest.skip(f"Skipping test: {str(e)}")

    @pytest.mark.asyncio
    async def test_browser_navigate(self) -> None:
        """Test page navigation functionality."""
        # Test case: navigate to valid URL
        result = await browser_navigate("https://www.example.com")
        assert result["status"] == "success", "Navigation to valid URL should succeed"
        assert "page_info" in result, "Should include page information"
        assert result["page_info"]["title"], "Should have page title"
        assert result["page_info"]["url"], "Should have page URL"
        assert result["page_info"]["content"], "Should have page content"

        # Test case: navigate to invalid URL
        result = await browser_navigate("https://invalid-url-that-does-not-exist.com")
        assert result["status"] == "error", "Navigation to invalid URL should fail"
        assert "message" in result, "Should include error message"

    @pytest.mark.asyncio
    async def test_browser_search(self) -> None:
        """Test search functionality."""
        # Test case: basic search with Bing
        result = await browser_search(
            query="test search",
            search_engine="bing",
            num_results=2
        )
        assert isinstance(result, dict), "Search result should be dictionary type"
        assert "results" in result, "Should contain search results"
        assert len(result["results"]) <= 2, "Result count should match specified value"
        assert "summary" in result, "Should contain search summary"
        assert "query" in result, "Should contain search query"

        # Test case: search with invalid engine
        result = await browser_search(
            query="test search",
            search_engine="invalid_engine",
            num_results=1
        )
        assert isinstance(result, dict), "Should return dictionary even with invalid search engine"
        assert "results" in result, "Should still contain search results using default engine"

    @pytest.mark.asyncio
    async def test_browser_click_and_hover(self) -> None:
        """Test click and hover functionality."""
        # First navigate to a test page
        await browser_navigate("https://www.example.com")

        # Test click functionality
        result = await browser_click("a")  # Click first link
        assert "成功点击元素" in result, "Should indicate successful click"

        # Test hover functionality
        result = await browser_hover("a")  # Hover over first link
        assert "成功悬停在元素上" in result, "Should indicate successful hover"

    @pytest.mark.asyncio
    async def test_browser_type(self) -> None:
        """Test typing functionality."""
        # Navigate to a page with input field
        await browser_navigate("https://www.example.com")
        
        # Test typing into an input field
        result = await browser_type("input", "test text")
        assert "成功在元素" in result, "Should indicate successful typing"

    @pytest.mark.asyncio
    async def test_browser_snapshot(self) -> None:
        """Test snapshot functionality."""
        # Navigate to a test page
        await browser_navigate("https://www.example.com")
        
        # Take snapshot
        result = await browser_snapshot()
        assert isinstance(eval(result), dict), "Snapshot should be a dictionary"
        snapshot = eval(result)
        assert "title" in snapshot, "Snapshot should contain page title"
        assert "url" in snapshot, "Snapshot should contain page URL"
        assert "text" in snapshot, "Snapshot should contain page text"

    @pytest.mark.asyncio
    async def test_browser_tab_operations(self) -> None:
        """Test tab operations functionality."""
        # Test new tab creation
        result = await browser_tab_new("https://www.example.com")
        assert "已打开新标签" in result, "Should indicate successful tab creation"

        # Test tab listing
        result = await browser_tab_list()
        tab_list = eval(result)
        assert isinstance(tab_list, list), "Tab list should be a list"
        assert len(tab_list) > 0, "Should have at least one tab"

        # Test tab closing
        result = await browser_tab_close()
        assert "已关闭标签" in result, "Should indicate successful tab closure"

    @pytest.mark.asyncio
    async def test_browser_screenshot(self) -> None:
        """Test screenshot functionality."""
        # Navigate to a test page
        await browser_navigate("https://www.example.com")
        
        # Test screenshot with base64 return
        result = await browser_take_screenshot()
        assert result.startswith("data:image/png;base64,"), "Should return base64 encoded image"

        # Test screenshot with file save
        test_path = "test_screenshot.png"
        try:
            result = await browser_take_screenshot(path=test_path)
            assert "截图已保存到" in result, "Should indicate successful screenshot save"
            assert os.path.exists(test_path), "Screenshot file should exist"
        finally:
            # Clean up test file
            if os.path.exists(test_path):
                os.remove(test_path)

if __name__ == '__main__':
    pytest.main(['-v', __file__])