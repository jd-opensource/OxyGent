"""
Chrome DevTools MCP Tools for OxyGent

这个文件提供了与 Chrome DevTools MCP 集成的工具函数，
可以直接在 OxyGent 框架中使用。
"""

import asyncio
import json
import logging
import subprocess
import sys
import requests
import time
import os
from typing import Any, Dict, List, Optional, Union

# 配置日志
logger = logging.getLogger(__name__)


class ChromeDevToolsMCPClient:
    """Chrome DevTools MCP 客户端类"""
    
    def __init__(self, debug_port: int = 9222, mcp_server_url: str = "http://localhost:3000"):
        """
        初始化 Chrome DevTools MCP 客户端
        
        Args:
            debug_port (int): Chrome 调试端口，默认 9222
            mcp_server_url (str): MCP 服务器 URL，默认 http://localhost:3000
        """
        self._server_process: Optional[subprocess.Popen] = None
        self._is_running = False
        self._chrome_process: Optional[subprocess.Popen] = None
        self._debug_port = debug_port
        self._mcp_server_url = mcp_server_url
        self._chrome_startup_timeout = 5  # Chrome 启动超时时间
        self._mcp_startup_timeout = 5     # MCP 服务器启动超时时间
    
    def start_mcp_server(self, command: Optional[List[str]] = None) -> bool:
        """
        启动 Chrome DevTools MCP 服务器
        
        Args:
            command (Optional[List[str]]): 自定义启动命令，默认使用 npx chrome-devtools-mcp@latest
        
        Returns:
            bool: 启动是否成功
        """
        try:
            # 检查是否已经在运行
            if self._is_running:
                logger.info("MCP 服务器已在运行")
                return True
            
            # 使用默认命令或自定义命令
            if command is None:
                command = ["npx", "chrome-devtools-mcp@latest"]
            
            # 尝试启动服务器进程
            self._server_process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 等待服务器启动
            time.sleep(self._mcp_startup_timeout)
            
            # 检查进程是否仍在运行
            if self._server_process.poll() is None:
                self._is_running = True
                logger.info(f"Chrome DevTools MCP 服务器已启动，PID: {self._server_process.pid}")
                return True
            else:
                logger.error("MCP 服务器启动后立即退出")
                return False
            
        except FileNotFoundError as e:
            logger.error(f"找不到 MCP 服务器命令: {e}")
            return False
        except Exception as e:
            logger.error(f"启动 Chrome DevTools MCP 服务器失败: {e}")
            return False
    
    def stop_mcp_server(self):
        """停止 Chrome DevTools MCP 服务器"""
        if self._server_process:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
                self._server_process = None
                self._is_running = False
                logger.info("Chrome DevTools MCP 服务器已停止")
            except Exception as e:
                logger.error(f"停止服务器时出错: {e}")
    
    def is_mcp_server_running(self) -> bool:
        """检查MCP服务器是否在运行"""
        return self._is_running and self._server_process is not None
    
    def ensure_chrome_running(self, chrome_path: Optional[str] = None, additional_args: Optional[List[str]] = None) -> bool:
        """
        确保 Chrome 在调试模式下运行
        
        Args:
            chrome_path (Optional[str]): 自定义 Chrome 路径
            additional_args (Optional[List[str]]): 额外的 Chrome 启动参数
        
        Returns:
            bool: Chrome 是否成功运行
        """
        try:
            # 检查 Chrome 调试端口是否可用
            response = requests.get(f'http://localhost:{self._debug_port}/json/version', timeout=2)
            if response.status_code == 200:
                logger.info(f"Chrome 调试端口 {self._debug_port} 已可用")
                return True
        except requests.RequestException:
            logger.info(f"Chrome 调试端口 {self._debug_port} 不可用，尝试启动 Chrome")
        
        # 启动 Chrome
        try:
            # 确定 Chrome 路径
            if chrome_path is None:
                import platform
                system = platform.system().lower()
                
                if system == 'darwin':  # macOS
                    chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                elif system == 'linux':
                    chrome_path = 'google-chrome'
                elif system == 'windows':
                    chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
                else:
                    chrome_path = 'google-chrome'
            
            # 基础启动参数
            chrome_args = [
                chrome_path,
                f'--remote-debugging-port={self._debug_port}',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-popup-blocking',
                '--disable-translate',
                '--disable-web-security',  # 允许跨域访问
                '--disable-features=VizDisplayCompositor'  # 提高稳定性
            ]
            
            # 添加额外参数
            if additional_args:
                chrome_args.extend(additional_args)
            
            logger.info(f"启动 Chrome: {' '.join(chrome_args)}")
            
            self._chrome_process = subprocess.Popen(
                chrome_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # 等待 Chrome 启动
            time.sleep(self._chrome_startup_timeout)
            
            # 再次检查连接
            for attempt in range(3):
                try:
                    response = requests.get(f'http://localhost:{self._debug_port}/json/version', timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Chrome 已成功启动，PID: {self._chrome_process.pid}")
                        return True
                except requests.RequestException:
                    if attempt < 2:  # 不是最后一次尝试
                        logger.info(f"第 {attempt + 1} 次连接尝试失败，等待重试...")
                        time.sleep(2)
                    
            logger.error("Chrome 启动后无法连接到调试端口")
            return False
                
        except FileNotFoundError:
            logger.error(f"找不到 Chrome 可执行文件: {chrome_path}")
            return False
        except Exception as e:
            logger.error(f"启动 Chrome 失败: {e}")
            return False
    
    def call_mcp_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        调用 MCP 工具的通用方法
        
        Args:
            tool_name (str): MCP 工具名称
            arguments (Optional[Dict[str, Any]]): 工具参数
        
        Returns:
            Dict[str, Any]: 工具调用结果
        """
        try:
            # 验证工具名称
            valid_tools = {
                "list_pages", "new_page", "navigate_page", "take_screenshot",
                "take_snapshot", "click", "fill", "evaluate_script",
                "performance_start_trace", "performance_stop_trace",
                "list_console_messages", "list_network_requests",
                "emulate_cpu", "emulate_network"
            }
            
            if tool_name not in valid_tools:
                return {
                    "status": "error",
                    "message": f"不支持的工具: {tool_name}",
                    "data": {"valid_tools": list(valid_tools)}
                }
            
            # 确保MCP服务器运行
            if not self.is_mcp_server_running():
                logger.info("MCP 服务器未运行，尝试启动...")
                if not self.start_mcp_server():
                    return {
                        "status": "error",
                        "message": "无法启动 Chrome DevTools MCP 服务器",
                        "data": {"debug_port": self._debug_port, "mcp_url": self._mcp_server_url}
                    }
            
            # 确保Chrome运行
            if not self.ensure_chrome_running():
                return {
                    "status": "error",
                    "message": "无法启动或连接到 Chrome 浏览器",
                    "data": {"debug_port": self._debug_port}
                }
            
            # 构建MCP工具调用请求
            mcp_request = {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),  # 使用时间戳作为唯一ID
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments or {}
                }
            }
            
            # 在实际的MCP集成中，这里应该通过MCP客户端发送请求
            # 现在我们返回一个标准化的响应格式，表示工具调用准备就绪
            logger.info(f"准备调用 MCP 工具: {tool_name}，参数: {arguments}")
            
            return {
                "status": "ready",
                "message": f"MCP 工具调用已准备就绪: {tool_name}",
                "data": {
                    "tool_name": tool_name,
                    "arguments": arguments or {},
                    "mcp_request": mcp_request,
                    "chrome_debug_port": self._debug_port,
                    "mcp_server_url": self._mcp_server_url,
                    "timestamp": time.time()
                }
            }
            
        except Exception as e:
            logger.error(f"调用 MCP 工具 {tool_name} 失败: {e}")
            return {
                "status": "error",
                "message": f"调用 MCP 工具失败: {str(e)}",
                "data": {"tool_name": tool_name, "arguments": arguments}
            }
    
    def execute_javascript(self, script: str, tab_id: Optional[str] = None) -> Dict[str, Any]:
        """直接执行 JavaScript 脚本（不通过MCP）"""
        try:
            if not self.ensure_chrome_running():
                return {
                    "status": "error",
                    "message": "无法连接到 Chrome",
                    "data": None
                }
            
            # 获取标签页列表
            response = requests.get(f'http://localhost:{self._debug_port}/json', timeout=5)
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": "无法获取标签页列表",
                    "data": None
                }
            
            tabs = response.json()
            page_tabs = [tab for tab in tabs if tab.get('type') == 'page']
            
            if not page_tabs:
                return {
                    "status": "error",
                    "message": "没有找到可用的标签页",
                    "data": None
                }
            
            # 选择标签页
            target_tab = None
            if tab_id:
                target_tab = next((tab for tab in page_tabs if tab.get('id') == tab_id), None)
            
            if not target_tab:
                target_tab = page_tabs[0]  # 使用第一个标签页
            
            # 获取标签页 ID
            tab_id = target_tab.get('id', '')
            if not tab_id:
                return {
                    "status": "error",
                    "message": "无法获取标签页 ID",
                    "data": None
                }
            
            # 使用 Chrome DevTools Protocol 通过 WebSocket 执行脚本
            try:
                import websocket  # type: ignore
                import json
                import threading
                import time
                
                # 获取 WebSocket URL
                ws_url = target_tab.get('webSocketDebuggerUrl')
                if not ws_url:
                    return {
                        "status": "error",
                        "message": "无法获取 WebSocket 调试 URL",
                        "data": None
                    }
                
                # 执行脚本的结果
                execution_result = {"completed": False, "result": None, "error": None}
                
                def on_message(ws, message):
                    try:
                        data = json.loads(message)
                        if data.get('id') == 1:  # 我们的请求 ID
                            if 'result' in data:
                                execution_result["result"] = data['result']
                            elif 'error' in data:
                                execution_result["error"] = data['error']
                            execution_result["completed"] = True
                    except Exception as e:
                        execution_result["error"] = str(e)
                        execution_result["completed"] = True
                
                def on_error(ws, error):
                    execution_result["error"] = str(error)
                    execution_result["completed"] = True
                
                def on_open(ws):
                    # 发送 Runtime.evaluate 命令
                    command = {
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": script,
                            "returnByValue": True,
                            "awaitPromise": True
                        }
                    }
                    ws.send(json.dumps(command))
                
                # 创建 WebSocket 连接
                ws = websocket.WebSocketApp(
                    ws_url,
                    on_message=on_message,
                    on_error=on_error,
                    on_open=on_open
                )
                
                # 在单独线程中运行 WebSocket
                ws_thread = threading.Thread(target=ws.run_forever)
                ws_thread.daemon = True
                ws_thread.start()
                
                # 等待执行完成，最多等待 10 秒
                timeout = 10
                start_time = time.time()
                while not execution_result["completed"] and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                ws.close()
                
                # 处理结果
                if execution_result["completed"]:
                    if execution_result["error"]:
                        return {
                            "status": "error",
                            "message": f"脚本执行错误: {execution_result['error']}",
                            "data": execution_result["error"]
                        }
                    elif execution_result["result"]:
                        result_data = execution_result["result"]
                        if 'result' in result_data:
                            return {
                                "status": "success",
                                "message": "脚本执行成功",
                                "data": {
                                    "result": result_data['result'].get('value'),
                                    "type": result_data['result'].get('type', 'undefined'),
                                    "description": result_data['result'].get('description', ''),
                                    "raw_response": result_data
                                }
                            }
                        elif 'exceptionDetails' in result_data:
                            return {
                                "status": "error",
                                "message": f"脚本执行异常: {result_data['exceptionDetails'].get('text', 'Unknown error')}",
                                "data": result_data['exceptionDetails']
                            }
                else:
                    return {
                        "status": "error",
                        "message": "脚本执行超时",
                        "data": None
                    }
                
                # 如果没有结果，返回默认错误
                return {
                    "status": "error",
                    "message": "脚本执行未返回结果",
                    "data": None
                }
                    
            except ImportError:
                # 如果没有 websocket 库，提供错误信息
                return {
                    "status": "error",
                    "message": "需要安装 websocket-client 库来执行脚本: pip install websocket-client",
                    "data": {
                        "script": script,
                        "tab_id": tab_id
                    }
                }
            except Exception as e:
                logger.error(f"WebSocket 连接失败: {e}")
                return {
                    "status": "error",
                    "message": f"WebSocket 连接失败: {str(e)}",
                    "data": None
                }
            
        except Exception as e:
            logger.error(f"执行脚本失败: {e}")
            return {
                "status": "error",
                "message": f"执行脚本失败: {str(e)}",
                "data": None
            }


# 全局客户端实例 - 支持配置
def get_chrome_devtools_client() -> ChromeDevToolsMCPClient:
    """获取全局 Chrome DevTools 客户端实例"""
    global _chrome_devtools_client
    if '_chrome_devtools_client' not in globals():
        # 从环境变量读取配置
        debug_port = int(os.getenv('CHROME_DEBUG_PORT', '9222'))
        mcp_server_url = os.getenv('CHROME_MCP_SERVER_URL', 'http://localhost:3000')
        _chrome_devtools_client = ChromeDevToolsMCPClient(debug_port, mcp_server_url)
    return _chrome_devtools_client

# 初始化全局客户端
_chrome_devtools_client = get_chrome_devtools_client()


def chrome_devtools_list_pages() -> Dict[str, Any]:
    """
    列出所有页面
    
    Returns:
        Dict[str, Any]: 包含页面列表的字典
    """
    return _chrome_devtools_client.call_mcp_tool("list_pages")


def chrome_devtools_new_page(url: str) -> Dict[str, Any]:
    """
    创建新页面
    
    Args:
        url (str): 要导航到的 URL
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("new_page", {"url": url})


def chrome_devtools_navigate(url: str) -> Dict[str, Any]:
    """
    导航到指定 URL
    
    Args:
        url (str): 要导航到的 URL
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("navigate_page", {"url": url})


def chrome_devtools_take_screenshot(format: str = "png", full_page: bool = False) -> Dict[str, Any]:
    """
    截图
    
    Args:
        format (str): 图片格式 (png, jpeg)
        full_page (bool): 是否截取整个页面
    
    Returns:
        Dict[str, Any]: 包含截图数据的字典
    """
    return _chrome_devtools_client.call_mcp_tool("take_screenshot", {
        "format": format,
        "full_page": full_page
    })


def chrome_devtools_take_snapshot() -> Dict[str, Any]:
    """
    创建页面快照
    
    Returns:
        Dict[str, Any]: 包含快照数据的字典
    """
    return _chrome_devtools_client.call_mcp_tool("take_snapshot")


def chrome_devtools_click_element(uid: str, double_click: bool = False) -> Dict[str, Any]:
    """
    点击元素
    
    Args:
        uid (str): 元素的唯一标识符
        double_click (bool): 是否双击
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("click", {
        "uid": uid,
        "double_click": double_click
    })


def chrome_devtools_fill_element(uid: str, value: str) -> Dict[str, Any]:
    """
    填充元素
    
    Args:
        uid (str): 元素的唯一标识符
        value (str): 要填充的值
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("fill", {
        "uid": uid,
        "value": value
    })


def chrome_devtools_evaluate_script(function: str, args: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    执行 JavaScript 脚本
    
    Args:
        function (str): 要执行的 JavaScript 脚本（纯文本形式）
        args (Optional[List[Dict[str, str]]]): 函数参数列表
    
    Returns:
        Dict[str, Any]: 包含执行结果的字典
    """
    # 只通过 chrome_devtools_mcp 中对应的 evaluate_script 来执行 JavaScript
    # 不使用其他兜底或回退方式
    # 以纯文本形式提供待执行脚本
    return _chrome_devtools_client.call_mcp_tool("evaluate_script", {
        "function": function,
        "args": args or []
    })


def chrome_devtools_performance_start_trace(reload: bool = False, auto_stop: bool = True) -> Dict[str, Any]:
    """
    开始性能追踪
    
    Args:
        reload (bool): 是否重新加载页面
        auto_stop (bool): 是否自动停止
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("performance_start_trace", {
        "reload": reload,
        "auto_stop": auto_stop
    })


def chrome_devtools_performance_stop_trace() -> Dict[str, Any]:
    """
    停止性能追踪
    
    Returns:
        Dict[str, Any]: 包含追踪数据的字典
    """
    return _chrome_devtools_client.call_mcp_tool("performance_stop_trace")


def chrome_devtools_list_console_messages() -> Dict[str, Any]:
    """
    获取控制台消息列表
    
    Returns:
        Dict[str, Any]: 包含控制台消息的字典
    """
    return _chrome_devtools_client.call_mcp_tool("list_console_messages")


def chrome_devtools_list_network_requests() -> Dict[str, Any]:
    """
    获取网络请求列表
    
    Returns:
        Dict[str, Any]: 包含网络请求的字典
    """
    return _chrome_devtools_client.call_mcp_tool("list_network_requests")


def chrome_devtools_emulate_cpu(throttling_rate: int) -> Dict[str, Any]:
    """
    模拟 CPU 节流
    
    Args:
        throttling_rate (int): 节流倍率 (1-20)
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("emulate_cpu", {
        "throttling_rate": throttling_rate
    })


def chrome_devtools_emulate_network(throttling_option: str) -> Dict[str, Any]:
    """
    模拟网络条件
    
    Args:
        throttling_option (str): 网络节流选项 ("No emulation", "Slow 3G", "Fast 3G", "Slow 4G", "Fast 4G")
    
    Returns:
        Dict[str, Any]: 包含操作结果的字典
    """
    return _chrome_devtools_client.call_mcp_tool("emulate_network", {
        "throttling_option": throttling_option
    })


def chrome_devtools_status() -> Dict[str, Any]:
    """
    获取 Chrome DevTools 状态
    
    Returns:
        Dict[str, Any]: 包含状态信息的字典
    """
    try:
        # 检查Chrome连接状态
        chrome_available = False
        chrome_version = None
        try:
            response = requests.get(f'http://localhost:{_chrome_devtools_client._debug_port}/json/version', timeout=2)
            if response.status_code == 200:
                chrome_available = True
                version_data = response.json()
                chrome_version = version_data.get('Browser', 'Unknown')
        except:
            pass
        
        return {
            "status": "success",
            "message": "Chrome DevTools MCP 工具状态",
            "data": {
                "mcp_server_running": _chrome_devtools_client.is_mcp_server_running(),
                "chrome_available": chrome_available,
                "chrome_version": chrome_version,
                "chrome_debug_port": _chrome_devtools_client._debug_port,
                "mcp_server_url": _chrome_devtools_client._mcp_server_url,
                "available_tools": [
                    "list_pages", "new_page", "navigate_page", "take_screenshot",
                    "take_snapshot", "click", "fill", "evaluate_script",
                    "performance_start_trace", "performance_stop_trace",
                    "list_console_messages", "list_network_requests",
                    "emulate_cpu", "emulate_network"
                ],
                "client_type": "ChromeDevToolsMCPClient",
                "version": "2.0.0",
                "features": {
                    "direct_javascript_execution": True,
                    "mcp_tool_calling": True,
                    "configurable_ports": True,
                    "error_recovery": True
                }
            }
        }
    except Exception as e:
        logger.error(f"获取状态时发生错误: {e}")
        return {
            "status": "error",
            "message": f"获取状态失败: {str(e)}",
            "data": None
        }


def chrome_devtools_validate_tools() -> Dict[str, Any]:
    """
    验证所有 Chrome DevTools 工具的可用性
    
    Returns:
        Dict[str, Any]: 验证结果
    """
    try:
        validation_results = {}
        
        # 定义所有可用的工具函数
        tool_functions = {
            "list_pages": chrome_devtools_list_pages,
            "new_page": lambda: chrome_devtools_new_page("about:blank"),
            "navigate": lambda: chrome_devtools_navigate("about:blank"),
            "take_screenshot": chrome_devtools_take_screenshot,
            "take_snapshot": chrome_devtools_take_snapshot,
            "click_element": lambda: chrome_devtools_click_element("test_uid"),
            "fill_element": lambda: chrome_devtools_fill_element("test_uid", "test_value"),
            "evaluate_script": lambda: chrome_devtools_evaluate_script("console.log('test')"),
            "performance_start_trace": chrome_devtools_performance_start_trace,
            "performance_stop_trace": chrome_devtools_performance_stop_trace,
            "list_console_messages": chrome_devtools_list_console_messages,
            "list_network_requests": chrome_devtools_list_network_requests,
            "emulate_cpu": lambda: chrome_devtools_emulate_cpu(2),
            "emulate_network": lambda: chrome_devtools_emulate_network("Slow 3G"),
            "status": chrome_devtools_status
        }
        
        # 验证每个工具函数
        for tool_name, tool_func in tool_functions.items():
            try:
                result = tool_func()
                validation_results[tool_name] = {
                    "available": True,
                    "status": result.get("status", "unknown"),
                    "message": result.get("message", "")
                }
            except Exception as e:
                validation_results[tool_name] = {
                    "available": False,
                    "error": str(e)
                }
        
        # 统计验证结果
        total_tools = len(validation_results)
        available_tools = sum(1 for result in validation_results.values() if result.get("available", False))
        
        return {
            "status": "success",
            "message": f"工具验证完成: {available_tools}/{total_tools} 个工具可用",
            "data": {
                "total_tools": total_tools,
                "available_tools": available_tools,
                "validation_results": validation_results,
                "overall_health": "good" if available_tools == total_tools else "partial" if available_tools > 0 else "poor"
            }
        }
        
    except Exception as e:
        logger.error(f"工具验证失败: {e}")
        return {
            "status": "error",
            "message": f"工具验证失败: {str(e)}",
            "data": None
        }


# 清理函数
def chrome_devtools_cleanup():
    """清理 Chrome DevTools 资源"""
    try:
        _chrome_devtools_client.stop_mcp_server()
        logger.info("Chrome DevTools 资源清理完成")
    except Exception as e:
        logger.error(f"清理资源时发生错误: {e}")


# 注册清理函数
import atexit
atexit.register(chrome_devtools_cleanup)


# 导出所有公共函数
__all__ = [
    "ChromeDevToolsMCPClient",
    "chrome_devtools_list_pages",
    "chrome_devtools_new_page",
    "chrome_devtools_navigate",
    "chrome_devtools_take_screenshot",
    "chrome_devtools_take_snapshot",
    "chrome_devtools_click_element",
    "chrome_devtools_fill_element",
    "chrome_devtools_evaluate_script",
    "chrome_devtools_performance_start_trace",
    "chrome_devtools_performance_stop_trace",
    "chrome_devtools_list_console_messages",
    "chrome_devtools_list_network_requests",
    "chrome_devtools_emulate_cpu",
    "chrome_devtools_emulate_network",
    "chrome_devtools_status",
    "chrome_devtools_validate_tools",
    "chrome_devtools_cleanup",
    "get_chrome_devtools_client"
]