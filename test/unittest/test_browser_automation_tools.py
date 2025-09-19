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


# ────────────────────────────────────────────────────────────────────────────
# Direct Execution Test Examples
# ────────────────────────────────────────────────────────────────────────────

def run_direct_test_examples():
    """
    直接执行的测试示例
    
    依赖要求:
    1. 安装 Playwright: pip install playwright
    2. 安装浏览器驱动: playwright install
    3. 确保网络连接正常
    
    测试环境要求:
    - Python 3.8+
    - 可访问互联网
    - 足够的磁盘空间用于截图保存
    """
    import asyncio
    import json
    import os
    from pathlib import Path
    
    async def test_basic_navigation():
        """测试基本的网页导航功能"""
        print("🧪 测试 1: 基本网页导航")
        try:
            result = await navigate_to_url("https://httpbin.org")
            result_data = json.loads(result)
            
            if result_data["status"] == "success":
                print(f"✅ 导航成功: {result_data['title']}")
                print(f"   URL: {result_data['url']}")
            else:
                print(f"❌ 导航失败: {result_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    async def test_content_extraction():
        """测试内容提取功能"""
        print("\n🧪 测试 2: 内容提取")
        try:
            result = await extract_page_content("https://httpbin.org", max_length=500)
            result_data = json.loads(result)
            
            if result_data["status"] == "success":
                print(f"✅ 内容提取成功")
                print(f"   内容长度: {result_data['length']} 字符")
                print(f"   前100字符: {result_data['content'][:100]}...")
            else:
                print(f"❌ 内容提取失败: {result_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    async def test_screenshot():
        """测试截图功能"""
        print("\n🧪 测试 3: 网页截图")
        try:
            # 确保输出目录存在
            output_dir = Path("test_screenshots")
            output_dir.mkdir(exist_ok=True)
            screenshot_path = output_dir / "test_httpbin_screenshot.png"
            
            result = await take_screenshot("https://httpbin.org", str(screenshot_path))
            result_data = json.loads(result)
            
            if result_data["status"] == "success":
                print(f"✅ 截图成功")
                print(f"   保存路径: {result_data['screenshot_path']}")
                if os.path.exists(result_data['screenshot_path']):
                    file_size = os.path.getsize(result_data['screenshot_path'])
                    print(f"   文件大小: {file_size} bytes")
            else:
                print(f"❌ 截图失败: {result_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    async def test_links_extraction():
        """测试链接提取功能"""
        print("\n🧪 测试 4: 链接提取")
        try:
            result = await get_page_links("https://httpbin.org", max_links=5)
            result_data = json.loads(result)
            
            if result_data["status"] == "success":
                print(f"✅ 链接提取成功")
                print(f"   总链接数: {result_data['total_links']}")
                for i, link in enumerate(result_data['links'][:3], 1):
                    print(f"   {i}. {link['text'][:50]}... -> {link['href']}")
            else:
                print(f"❌ 链接提取失败: {result_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    async def run_all_tests():
        """运行所有直接测试"""
        print("=" * 60)
        print("🚀 OxyGent 浏览器自动化工具 - 直接执行测试")
        print("=" * 60)
        print("\n📋 测试环境检查:")
        
        # 检查 Playwright 是否已安装
        try:
            from playwright.async_api import async_playwright
            print("✅ Playwright 已安装")
        except ImportError:
            print("❌ Playwright 未安装")
            print("   请运行: pip install playwright")
            print("   然后运行: playwright install")
            return
        
        # 检查网络连接
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            print("✅ 网络连接正常")
        except OSError:
            print("⚠️ 网络连接可能存在问题")
        
        print("\n开始执行测试...\n")
        
        await test_basic_navigation()
        await test_content_extraction()
        await test_screenshot()
        await test_links_extraction()
        
        print("\n" + "=" * 60)
        print("🎯 测试完成!")
        print("=" * 60)
        print("\n💡 如需进一步测试，请运行:")
        print("   python -m pytest test/unittest/test_browser_automation_tools.py -v")
        print("\n📁 截图文件保存在: ./test_screenshots/")
    
    # 运行测试
    asyncio.run(run_all_tests())


if __name__ == "__main__":
    print("🔧 运行浏览器自动化工具直接测试示例")
    print("\n⚠️  注意: 这将执行真实的浏览器操作，需要:")
    print("   1. pip install playwright")
    print("   2. playwright install")
    print("   3. 网络连接")
    print("\n按 Enter 继续，或 Ctrl+C 取消...")
    
    try:
        input()
        run_direct_test_examples()
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
