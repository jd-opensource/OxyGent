"""
MCP Server for Browser Operations

This file provides browser automation tools that can be invoked by an agent.
It includes tools for navigating web pages, interacting with elements,
capturing screenshots, and managing browser tabs using the Playwright framework.
"""

import asyncio
import base64
import importlib
import os
from typing import Dict, List, Optional, Any, Literal
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Initialize FastMCP server instance
mcp = FastMCP()

# 全局变量，用于存储浏览器实例和页面
_browser = None
_context = None
_pages = {}  # 存储页面的字典，键为页面ID，值为页面对象
_current_page_id = None  # 当前活动页面的ID
_data_ready = False  # 标记数据是否已准备好
_operation_in_progress = False  # 标记操作是否正在进行中


# 检查必要的依赖是否已安装
def check_dependencies():
    missing_deps = []
    
    # 检查playwright
    try:
        importlib.import_module('playwright')
    except ImportError:
        missing_deps.append('playwright')
    
    return missing_deps


async def _ensure_browser():
    """确保浏览器已启动"""
    global _browser, _context
    
    if _browser is None:
        try:
            # 动态导入playwright，避免启动时的导入错误
            playwright_module = importlib.import_module('playwright.async_api')
            async_playwright = playwright_module.async_playwright
            
            playwright = await async_playwright().start()
            _browser = await playwright.chromium.launch(headless=True)
            _context = await _browser.new_context()
        except ImportError:
            raise ImportError("请安装playwright: pip install playwright，然后运行: playwright install")
        except Exception as e:
            raise Exception(f"启动浏览器时发生错误: {str(e)}")


async def _ensure_page():
    """确保至少有一个页面打开，并返回当前页面"""
    global _pages, _current_page_id
    
    await _ensure_browser()
    
    if not _pages or _current_page_id not in _pages:
        # 确保_context已初始化
        if _context is None:
            await _ensure_browser()
        
        # 此时_context应该已经初始化，但为了类型检查，我们再次验证
        if _context is not None:
            page = await _context.new_page()
            page_id = f"page_{len(_pages) + 1}"
            _pages[page_id] = page
            _current_page_id = page_id
        else:
            raise Exception("无法初始化浏览器上下文")
    
    return _pages[_current_page_id]


async def _close_browser():
    """关闭浏览器"""
    global _browser, _context, _pages, _current_page_id, _data_ready, _operation_in_progress
    
    if _browser:
        for page_id in list(_pages.keys()):
            if _pages[page_id]:
                await _pages[page_id].close()
        
        _pages = {}
        _current_page_id = None
        _data_ready = False
        _operation_in_progress = False
        
        if _context:
            await _context.close()
        
        await _browser.close()
        _browser = None
        _context = None


async def _set_operation_status(in_progress=True):
    """设置操作状态"""
    global _operation_in_progress, _data_ready
    _operation_in_progress = in_progress
    if in_progress:
        _data_ready = False

async def _verify_data_ready():
    """验证数据是否已准备好"""
    global _data_ready
    _data_ready = True
    return _data_ready

@mcp.tool(description="导航到指定URL并获取页面内容")
async def browser_navigate(url: str = Field(description="要导航到的网页URL"),
                          wait_until: str = Field(default="load", description="等待页面加载的条件，可选值: 'load', 'domcontentloaded', 'networkidle'"),
                          extract_content: bool = Field(default=True, description="是否提取页面内容")):
    """
    导航到指定的URL，等待页面加载完成，并自动提取页面主要内容
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        
        # 验证wait_until参数
        valid_wait_options = ["load", "domcontentloaded", "networkidle"]
        if wait_until not in valid_wait_options:
            wait_until = "load"
        
        # 导航到URL
        response = await page.goto(url, wait_until=wait_until)
        
        # 等待页面稳定
        await asyncio.sleep(1)
        
        # 获取页面信息
        page_info = {}
        if extract_content:
            # 获取页面标题
            page_info["title"] = await page.title()
            
            # 获取页面URL（可能因重定向而改变）
            page_info["url"] = page.url
            
            # 提取页面主要内容
            try:
                # 提取页面文本内容
                page_text = await page.evaluate("""() => {
                    // 尝试获取主要内容区域
                    const mainContent = document.querySelector('main') ||
                                        document.querySelector('article') ||
                                        document.querySelector('#content') ||
                                        document.querySelector('.content') ||
                                        document.body;
                    
                    // 如果找到主要内容区域，则返回其文本
                    if (mainContent) {
                        return mainContent.innerText;
                    }
                    
                    // 否则返回页面所有文本
                    return document.body.innerText;
                }""")
                
                # 如果文本太长，截取前3000个字符
                if len(page_text) > 3000:
                    page_info["content"] = page_text[:3000] + "...(内容已截断)"
                else:
                    page_info["content"] = page_text
                
                # 提取页面元数据
                meta_data = await page.evaluate("""() => {
                    const metadata = {};
                    
                    // 获取所有meta标签
                    const metaTags = document.querySelectorAll('meta');
                    for (const meta of metaTags) {
                        const name = meta.getAttribute('name') || meta.getAttribute('property');
                        const content = meta.getAttribute('content');
                        if (name && content) {
                            metadata[name] = content;
                        }
                    }
                    
                    return metadata;
                }""")
                
                # 提取重要的元数据
                important_meta = ["description", "keywords", "og:title", "og:description"]
                page_info["metadata"] = {}
                for key in important_meta:
                    if key in meta_data:
                        page_info["metadata"][key] = meta_data[key]
                
                # 提取页面上的主要链接
                links = await page.evaluate("""() => {
                    const mainLinks = [];
                    const links = document.querySelectorAll('a');
                    
                    // 只获取前10个重要链接
                    let count = 0;
                    for (const link of links) {
                        if (count >= 10) break;
                        
                        const href = link.getAttribute('href');
                        const text = link.innerText.trim();
                        
                        // 过滤掉空链接和无文本链接
                        if (href && text && href !== '#' && !href.startsWith('javascript:')) {
                            mainLinks.push({ text, href });
                            count++;
                        }
                    }
                    
                    return mainLinks;
                }""")
                
                page_info["main_links"] = links
                
            except Exception as content_error:
                page_info["content_error"] = f"提取页面内容时发生错误: {str(content_error)}"
        
        await _verify_data_ready()
        
        if response:
            result = {
                "status": "success",
                "status_code": response.status,
                "url": url,
                "final_url": page.url,
                "message": f"成功导航到 {url}，状态码: {response.status}，数据已准备就绪"
            }
            
            # 如果提取了页面内容，则添加到结果中
            if extract_content and page_info:
                result["page_info"] = page_info
            
            await _set_operation_status(False)
            return result
        else:
            await _set_operation_status(False)
            return {
                "status": "error",
                "url": url,
                "message": f"导航到 {url} 失败，未收到响应"
            }
    except Exception as e:
        await _set_operation_status(False)
        return {
            "status": "error",
            "url": url,
            "message": f"导航到 {url} 时发生错误: {str(e)}"
        }


@mcp.tool(description="返回上一页")
async def browser_navigate_back():
    """
    返回浏览器历史记录中的上一页
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        await page.go_back()
        
        # 等待页面稳定
        await asyncio.sleep(1)
        await _verify_data_ready()
        
        await _set_operation_status(False)
        return "成功返回上一页，数据已准备就绪"
    except Exception as e:
        await _set_operation_status(False)
        return f"返回上一页时发生错误: {str(e)}"


@mcp.tool(description="前进到下一页")
async def browser_navigate_forward():
    """
    前进到浏览器历史记录中的下一页
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        await page.go_forward()
        
        # 等待页面稳定
        await asyncio.sleep(1)
        await _verify_data_ready()
        
        await _set_operation_status(False)
        return "成功前进到下一页，数据已准备就绪"
    except Exception as e:
        await _set_operation_status(False)
        return f"前进到下一页时发生错误: {str(e)}"


@mcp.tool(description="点击元素")
async def browser_click(selector: str = Field(description="要点击的元素的CSS选择器"),
                       timeout: int = Field(default=5000, description="等待元素出现的超时时间(毫秒)")):
    """
    点击页面上的元素
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        
        # 等待元素出现
        await page.wait_for_selector(selector, timeout=timeout)
        
        # 点击元素
        await page.click(selector)
        
        # 等待可能的页面变化
        await asyncio.sleep(1)
        await _verify_data_ready()
        
        await _set_operation_status(False)
        return f"成功点击元素: {selector}，数据已准备就绪"
    except Exception as e:
        await _set_operation_status(False)
        return f"点击元素 {selector} 时发生错误: {str(e)}"


@mcp.tool(description="悬停在元素上")
async def browser_hover(selector: str = Field(description="要悬停的元素的CSS选择器"),
                       timeout: int = Field(default=5000, description="等待元素出现的超时时间(毫秒)")):
    """
    将鼠标悬停在页面上的元素上
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        
        # 等待元素出现
        await page.wait_for_selector(selector, timeout=timeout)
        
        # 悬停在元素上
        await page.hover(selector)
        
        # 等待可能的页面变化（如悬停菜单出现）
        await asyncio.sleep(0.5)
        await _verify_data_ready()
        
        await _set_operation_status(False)
        return f"成功悬停在元素上: {selector}，数据已准备就绪"
    except Exception as e:
        await _set_operation_status(False)
        return f"悬停在元素 {selector} 上时发生错误: {str(e)}"


@mcp.tool(description="在元素中输入文本")
async def browser_type(selector: str = Field(description="要输入文本的元素的CSS选择器"),
                      text: str = Field(description="要输入的文本"),
                      timeout: int = Field(default=5000, description="等待元素出现的超时时间(毫秒)")):
    """
    在页面上的元素中输入文本
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        
        # 等待元素出现
        await page.wait_for_selector(selector, timeout=timeout)
        
        # 清除现有文本
        await page.fill(selector, "")
        
        # 输入文本
        await page.type(selector, text)
        await _verify_data_ready()
        
        await _set_operation_status(False)
        return f"成功在元素 {selector} 中输入文本，数据已准备就绪"
    except Exception as e:
        await _set_operation_status(False)
        return f"在元素 {selector} 中输入文本时发生错误: {str(e)}"


@mcp.tool(description="捕获页面的可访问性快照")
async def browser_snapshot():
    """
    捕获页面的可访问性快照，包括页面标题、URL和内容
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        
        # 获取页面信息
        title = await page.title()
        url = page.url
        
        # 获取页面内容
        content = await page.content()
        
        # 提取页面文本
        text = await page.evaluate("""() => {
            return document.body.innerText;
        }""")
        
        # 如果文本太长，截取前2000个字符
        if len(text) > 2000:
            text = text[:2000] + "...(内容已截断)"
        
        snapshot = {
            "title": title,
            "url": url,
            "text": text,
            "data_complete": True
        }
        
        await _verify_data_ready()
        await _set_operation_status(False)
        return str(snapshot)
    except Exception as e:
        await _set_operation_status(False)
        return f"捕获页面快照时发生错误: {str(e)}"


@mcp.tool(description="截取页面截图")
async def browser_take_screenshot(path: str = Field(default="", description="保存截图的路径，如果为空则返回base64编码的图像数据"),
                                full_page: bool = Field(default=False, description="是否截取整个页面，而不仅仅是可见区域")):
    """
    截取当前页面的截图
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        page = await _ensure_page()
        
        # 等待页面稳定
        await asyncio.sleep(0.5)
        
        if path:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            # 截取截图并保存到文件
            await page.screenshot(path=path, full_page=full_page)
            await _verify_data_ready()
            await _set_operation_status(False)
            return f"截图已保存到: {path}，数据已准备就绪"
        else:
            # 截取截图并返回base64编码的数据
            screenshot_bytes = await page.screenshot(full_page=full_page)
            base64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
            await _verify_data_ready()
            await _set_operation_status(False)
            return f"data:image/png;base64,{base64_data}"
    except Exception as e:
        await _set_operation_status(False)
        return f"截取页面截图时发生错误: {str(e)}"


@mcp.tool(description="列出所有浏览器标签")
async def browser_tab_list():
    """
    列出所有打开的浏览器标签
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        await _ensure_browser()
        
        if not _pages:
            await _set_operation_status(False)
            return "没有打开的标签"
        
        tabs = []
        for page_id, page in _pages.items():
            try:
                title = await page.title()
                url = page.url
                is_current = page_id == _current_page_id
                
                tabs.append({
                    "id": page_id,
                    "title": title,
                    "url": url,
                    "is_current": is_current
                })
            except:
                # 页面可能已关闭
                pass
        
        await _verify_data_ready()
        await _set_operation_status(False)
        return str(tabs)
    except Exception as e:
        await _set_operation_status(False)
        return f"列出浏览器标签时发生错误: {str(e)}"


@mcp.tool(description="打开新标签")
async def browser_tab_new(url: str = Field(default="about:blank", description="在新标签中打开的URL")):
    """
    打开一个新的浏览器标签
    """
    global _pages, _current_page_id
    
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        await _ensure_browser()
        
        # 确保_context已初始化
        if _context is None:
            await _ensure_browser()
        
        # 此时_context应该已经初始化，但为了类型检查，我们再次验证
        if _context is not None:
            # 创建新页面
            page = await _context.new_page()
        else:
            raise Exception("无法初始化浏览器上下文")
        page_id = f"page_{len(_pages) + 1}"
        _pages[page_id] = page
        _current_page_id = page_id
        
        # 如果提供了URL，则导航到该URL
        if url != "about:blank":
            await page.goto(url)
            # 等待页面加载
            await asyncio.sleep(1)
        
        await _verify_data_ready()
        await _set_operation_status(False)
        return f"已打开新标签，ID: {page_id}，数据已准备就绪"
    except Exception as e:
        await _set_operation_status(False)
        return f"打开新标签时发生错误: {str(e)}"


@mcp.tool(description="关闭标签")
async def browser_tab_close(page_id: str = Field(default="", description="要关闭的标签ID，如果为空则关闭当前标签")):
    """
    关闭指定的浏览器标签
    """
    global _pages, _current_page_id
    
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    try:
        await _set_operation_status(True)
        await _ensure_browser()
        
        if not _pages:
            await _set_operation_status(False)
            return "没有打开的标签可关闭"
        
        # 确定要关闭的页面ID
        target_page_id = page_id if page_id and page_id in _pages else _current_page_id
        
        if target_page_id not in _pages:
            await _set_operation_status(False)
            return f"找不到ID为 {target_page_id} 的标签"
        
        # 关闭页面
        await _pages[target_page_id].close()
        del _pages[target_page_id]
        
        # 如果关闭的是当前页面，则切换到另一个页面
        if target_page_id == _current_page_id:
            if _pages:
                _current_page_id = next(iter(_pages))
            else:
                _current_page_id = None
        
        await _verify_data_ready()
        await _set_operation_status(False)
        return f"已关闭标签，ID: {target_page_id}，操作已完成"
    except Exception as e:
        await _set_operation_status(False)
        return f"关闭标签时发生错误: {str(e)}"




@mcp.tool(description="执行网络搜索并返回搜索结果及页面内容")
async def browser_search(
    query: str = Field(description="搜索查询"),
    search_engine: Literal["google", "bing", "baidu"] = Field(default="bing", description="搜索引擎，支持google、bing或baidu"),
    num_results: int = Field(default=5, description="返回的搜索结果数量，最大10个"),
    timeout: int = Field(default=30, description="搜索操作的超时时间(秒)"),
    extract_page_content: bool = Field(default=True, description="是否提取页面主要内容，用于二次确认")
):
    """
    使用指定的搜索引擎执行网络搜索，并返回结构化的搜索结果及页面主要内容
    """
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        return f"缺少必要的库: {', '.join(missing_deps)}。请使用pip安装: pip install {' '.join(missing_deps)}"
    
    # 限制结果数量在合理范围内
    if num_results < 1:
        num_results = 1
    elif num_results > 10:
        num_results = 10
    
    # 初始化结果变量
    results = []
    partial_results = False
    error_message = None
    
    await _set_operation_status(True)
    
    try:
        # 确保浏览器已启动
        page = await _ensure_page()
        
        # 编码搜索查询
        encoded_query = quote(query)
        
        # 根据选择的搜索引擎构建URL
        search_urls = {
            "google": f"https://www.google.com/search?q={encoded_query}",
            "bing": f"https://www.bing.com/search?q={encoded_query}",
            "baidu": f"https://www.baidu.com/s?wd={encoded_query}"
        }
        
        # 获取搜索URL
        search_url = search_urls.get(search_engine.lower(), search_urls["bing"])
        
        # 使用超时机制导航到搜索页面
        try:
            navigation_task = page.goto(search_url, wait_until="networkidle")
            await asyncio.wait_for(navigation_task, timeout=timeout)
        except asyncio.TimeoutError:
            # 如果导航超时，尝试继续处理已加载的内容
            error_message = f"导航到搜索页面超时(>{timeout}秒)，尝试处理已加载的内容"
        
        # 等待页面加载完成，但设置超时
        try:
            await asyncio.wait_for(asyncio.sleep(2), timeout=3)
        except asyncio.TimeoutError:
            # 如果等待超时，继续处理
            pass
        
        # 根据不同的搜索引擎提取搜索结果，使用超时机制
        try:
            if search_engine.lower() == "google":
                # 提取Google搜索结果
                evaluation_task = page.evaluate(f"""(numResults) => {{
                    const searchResults = [];
                    const resultElements = document.querySelectorAll('div[data-sokoban-container]');
                    
                    for (let i = 0; i < resultElements.length && searchResults.length < numResults; i++) {{
                        const element = resultElements[i];
                        
                        // 尝试提取标题和链接
                        const titleElement = element.querySelector('h3');
                        if (!titleElement) continue;
                        
                        const linkElement = element.querySelector('a');
                        if (!linkElement) continue;
                        
                        const title = titleElement.innerText.trim();
                        const link = linkElement.href;
                        
                        // 尝试提取摘要
                        let snippet = '';
                        const snippetElement = element.querySelector('div[style*="webkit-line-clamp"]') ||
                                              element.querySelector('div[data-content-feature="1"]');
                        if (snippetElement) {{
                            snippet = snippetElement.innerText.trim();
                        }}
                        
                        if (title && link) {{
                            searchResults.push({{ title, link, snippet }});
                        }}
                    }}
                    
                    return searchResults;
                }}""", num_results)
                results = await asyncio.wait_for(evaluation_task, timeout=timeout/2)
                
            elif search_engine.lower() == "bing":
                # 提取Bing搜索结果
                evaluation_task = page.evaluate(f"""(numResults) => {{
                    const searchResults = [];
                    const resultElements = document.querySelectorAll('#b_results > li.b_algo');
                    
                    for (let i = 0; i < resultElements.length && searchResults.length < numResults; i++) {{
                        const element = resultElements[i];
                        
                        // 提取标题和链接
                        const titleElement = element.querySelector('h2 a');
                        if (!titleElement) continue;
                        
                        const title = titleElement.innerText.trim();
                        const link = titleElement.href;
                        
                        // 提取摘要
                        let snippet = '';
                        const snippetElement = element.querySelector('.b_caption p');
                        if (snippetElement) {{
                            snippet = snippetElement.innerText.trim();
                        }}
                        
                        if (title && link) {{
                            searchResults.push({{ title, link, snippet }});
                        }}
                    }}
                    
                    return searchResults;
                }}""", num_results)
                results = await asyncio.wait_for(evaluation_task, timeout=timeout/2)
                
            elif search_engine.lower() == "baidu":
                # 提取百度搜索结果
                evaluation_task = page.evaluate(f"""(numResults) => {{
                    const searchResults = [];
                    const resultElements = document.querySelectorAll('.result');
                    
                    for (let i = 0; i < resultElements.length && searchResults.length < numResults; i++) {{
                        const element = resultElements[i];
                        
                        // 提取标题和链接
                        const titleElement = element.querySelector('h3 a');
                        if (!titleElement) continue;
                        
                        const title = titleElement.innerText.trim();
                        const link = titleElement.href;
                        
                        // 提取摘要
                        let snippet = '';
                        const snippetElement = element.querySelector('.c-abstract');
                        if (snippetElement) {{
                            snippet = snippetElement.innerText.trim();
                        }}
                        
                        if (title && link) {{
                            searchResults.push({{ title, link, snippet }});
                        }}
                    }}
                    
                    return searchResults;
                }}""", num_results)
                results = await asyncio.wait_for(evaluation_task, timeout=timeout/2)
        except asyncio.TimeoutError:
            # 如果提取结果超时，记录错误并尝试使用通用提取方法
            error_message = f"提取搜索结果超时(>{timeout/2}秒)，尝试使用通用提取方法"
            partial_results = True
        
        # 如果没有找到结果或者提取超时，尝试通用提取方法
        if not results or len(results) == 0:
            try:
                evaluation_task = page.evaluate(f"""(numResults) => {{
                    const searchResults = [];
                    // 尝试查找所有可能的搜索结果元素
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    
                    // 过滤可能的搜索结果链接
                    const resultLinks = allLinks.filter(link => {{
                        // 链接应该有href属性
                        if (!link.href) return false;
                        
                        // 链接应该不是导航链接
                        if (link.href.includes('search?') ||
                            link.href.includes('javascript:') ||
                            link.href.includes('#')) return false;
                        
                        // 链接应该有文本内容
                        if (!link.innerText.trim()) return false;
                        
                        // 链接文本不应太短
                        if (link.innerText.trim().length < 15) return false;
                        
                        return true;
                    }});
                    
                    // 提取搜索结果
                    for (let i = 0; i < resultLinks.length && searchResults.length < numResults; i++) {{
                        const link = resultLinks[i];
                        const title = link.innerText.trim();
                        const url = link.href;
                        
                        // 尝试找到摘要（链接附近的文本）
                        let snippet = '';
                        const parent = link.parentElement;
                        if (parent) {{
                            const siblings = Array.from(parent.childNodes);
                            for (const sibling of siblings) {{
                                if (sibling !== link && sibling.textContent) {{
                                    const text = sibling.textContent.trim();
                                    if (text.length > 20) {{
                                        snippet = text;
                                        break;
                                    }}
                                }}
                            }}
                        }}
                        
                        searchResults.push({{ title, link: url, snippet }});
                    }}
                    
                    return searchResults;
                }}""", num_results)
                results = await asyncio.wait_for(evaluation_task, timeout=timeout/3)
            except asyncio.TimeoutError:
                # 如果通用提取方法也超时，记录错误
                if error_message:
                    error_message += "，通用提取方法也超时"
                else:
                    error_message = f"通用提取方法超时(>{timeout/3}秒)"
        
        # 构建搜索结果摘要
        summary = f"搜索查询: \"{query}\"\n"
        summary += f"搜索引擎: {search_engine}\n"
        
        if error_message:
            summary += f"警告: {error_message}\n"
        
        if partial_results:
            summary += "注意: 由于超时，可能只返回部分结果\n"
        
        summary += f"找到 {len(results)} 个结果\n\n"
        
        for i, result in enumerate(results):
            summary += f"{i+1}. {result.get('title', '无标题')}\n"
            summary += f"   链接: {result.get('link', '无链接')}\n"
            snippet = result.get('snippet', '')
            if snippet:
                if len(snippet) > 100:
                    snippet = snippet[:100] + "..."
                summary += f"   摘要: {snippet}\n"
            summary += '\n'
        
        # 提取页面主要内容（如果需要）
        page_content = {}
        if extract_page_content:
            try:
                # 获取页面标题
                page_content["title"] = await page.title()
                
                # 获取页面URL
                page_content["url"] = page.url
                
                # 提取页面主要内容
                page_text = await page.evaluate("""() => {
                    // 尝试获取主要内容区域
                    const mainContent = document.querySelector('main') ||
                                        document.querySelector('article') ||
                                        document.querySelector('#content') ||
                                        document.querySelector('.content') ||
                                        document.body;
                    
                    // 如果找到主要内容区域，则返回其文本
                    if (mainContent) {
                        return mainContent.innerText;
                    }
                    
                    // 否则返回页面所有文本
                    return document.body.innerText;
                }""")
                
                # 如果文本太长，截取前3000个字符
                if len(page_text) > 3000:
                    page_content["content"] = page_text[:3000] + "...(内容已截断)"
                else:
                    page_content["content"] = page_text
                
                # 提取页面元数据
                meta_data = await page.evaluate("""() => {
                    const metadata = {};
                    
                    // 获取所有meta标签
                    const metaTags = document.querySelectorAll('meta');
                    for (const meta of metaTags) {
                        const name = meta.getAttribute('name') || meta.getAttribute('property');
                        const content = meta.getAttribute('content');
                        if (name && content) {
                            metadata[name] = content;
                        }
                    }
                    
                    return metadata;
                }""")
                
                # 提取重要的元数据
                important_meta = ["description", "keywords", "og:title", "og:description"]
                page_content["metadata"] = {}
                for key in important_meta:
                    if key in meta_data:
                        page_content["metadata"][key] = meta_data[key]
                
            except Exception as content_error:
                page_content["content_error"] = f"提取页面内容时发生错误: {str(content_error)}"
        
        response = {
            "query": query,
            "search_engine": search_engine,
            "results": results,
            "summary": summary
        }
        
        if extract_page_content and page_content:
            response["page_content"] = page_content
        
        if error_message:
            response["error"] = error_message
            response["partial_results"] = partial_results
        
        return response
    except Exception as e:
        # 捕获所有其他异常
        error_msg = f"执行网络搜索时发生错误: {str(e)}"
        
        # 如果有部分结果，尝试返回
        if results and len(results) > 0:
            summary = f"搜索查询: \"{query}\"\n"
            summary += f"搜索引擎: {search_engine}\n"
            summary += f"警告: {error_msg}，返回部分结果\n"
            summary += f"找到 {len(results)} 个结果\n\n"
            
            for i, result in enumerate(results):
                summary += f"{i+1}. {result.get('title', '无标题')}\n"
                summary += f"   链接: {result.get('link', '无链接')}\n"
                snippet = result.get('snippet', '')
                if snippet:
                    if len(snippet) > 100:
                        snippet = snippet[:100] + "..."
                    summary += f"   摘要: {snippet}\n"
                summary += '\n'
            
            result = {
                "query": query,
                "search_engine": search_engine,
                "results": results,
                "summary": summary,
                "error": error_msg,
                "partial_results": True
            }
            
            # 在异常处理中，我们不尝试提取页面内容，因为页面可能已经不可用
            # 只添加一个说明，表明由于错误无法提取页面内容
            if extract_page_content:
                result["content_error"] = "由于发生错误，无法提取页面内容"
            
            return result
        else:
            return error_msg

# 添加一个工具来检查操作状态
@mcp.tool(description="检查浏览器操作状态")
async def browser_check_status():
    """
    检查浏览器操作状态，确认数据是否已准备就绪
    """
    global _operation_in_progress, _data_ready
    
    try:
        if _browser is None:
            return {
                "browser_initialized": False,
                "operation_in_progress": False,
                "data_ready": False,
                "message": "浏览器尚未初始化"
            }
        
        return {
            "browser_initialized": True,
            "operation_in_progress": _operation_in_progress,
            "data_ready": _data_ready,
            "active_pages": len(_pages),
            "message": "数据已准备就绪" if _data_ready else "操作正在进行中，数据尚未准备就绪"
        }
    except Exception as e:
        return f"检查浏览器状态时发生错误: {str(e)}"

# 注册关闭事件处理函数
# FastMCP可能没有on_shutdown方法，我们使用atexit模块来确保浏览器在程序退出时关闭
import atexit
import asyncio

# 创建一个同步函数来关闭浏览器
def close_browser_sync():
    global _operation_in_progress, _data_ready
    if _browser is not None:
        _operation_in_progress = False
        _data_ready = False
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_close_browser())
        else:
            loop.run_until_complete(_close_browser())

# 注册退出处理函数
atexit.register(close_browser_sync)


# Entry point: run the MCP server when script is executed directly
if __name__ == "__main__":
    mcp.run()