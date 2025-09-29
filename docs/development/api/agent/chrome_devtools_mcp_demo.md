# Chrome DevTools MCP 演示

## 概述

本目录包含了 Chrome DevTools MCP (Model Context Protocol) 工具的演示和使用示例。Chrome DevTools MCP 允许你通过编程方式控制 Chrome 浏览器，执行各种自动化任务。

## 演示文件

### 1. 界面化演示 (推荐) 🆕

- **文件**: `chrome_devtools_gui_demo.py`
- **启动脚本**: `run_chrome_gui_demo.sh`
- **描述**: 基于 OxyGent 框架的 Web 界面演示，支持智能体协作

#### 功能展示:

- 🌐 **Web 界面**: 提供友好的浏览器界面进行交互
- 🤖 **智能体协作**: Master Agent 协调 Chrome DevTools Agent 和 File Agent
- 🔧 **完整工具集**: 支持所有 26 个 Chrome DevTools 功能
- 📁 **文件操作**: 自动保存页面内容到本地文件
- 🎯 **任务导向**: 通过自然语言描述复杂的自动化任务

#### 运行方式:

```bash
# 设置环境变量 (必需)
export DEFAULT_LLM_API_KEY='your_api_key'
export DEFAULT_LLM_BASE_URL='your_base_url'
export DEFAULT_LLM_MODEL_NAME='your_model_name'

# 启动界面化演示
./examples/agents/run_chrome_gui_demo.sh
```

### 2. 简化演示

- **文件**: `simple_chrome_demo.py`
- **启动脚本**: `run_simple_demo.sh`
- **描述**: 独立的演示，不依赖完整的 OxyGent 框架

#### 功能展示:

- ✅ 列出 26 个可用工具
- ✅ 浏览器页面管理
- ✅ 页面快照获取
- ✅ 页面截图功能

#### 运行方式:

```bash
# 方法 1: 使用启动脚本 (推荐)
./examples/agents/run_simple_demo.sh

# 方法 2: 直接运行 Python 脚本
cd examples/agents
python3 simple_chrome_demo.py
```

### 3. 完整演示

- **文件**: `chrome_devtools_demo.py`
- **启动脚本**: `run_chrome_devtools_demo.sh`
- **描述**: 集成 OxyGent 框架的完整演示

## 可用工具列表

Chrome DevTools MCP 提供了 26 个强大的工具：

### 页面管理

- `list_pages` - 列出所有打开的页面
- `new_page` - 创建新页面
- `close_page` - 关闭指定页面
- `select_page` - 选择当前操作的页面
- `navigate_page` - 导航到指定 URL
- `navigate_page_history` - 前进/后退导航
- `resize_page` - 调整页面窗口大小

### 页面交互

- `click` - 点击页面元素
- `drag` - 拖拽元素
- `fill` - 填写表单字段
- `fill_form` - 批量填写表单
- `hover` - 鼠标悬停
- `upload_file` - 上传文件
- `wait_for` - 等待指定文本出现

### 页面分析

- `take_snapshot` - 获取页面文本快照
- `take_screenshot` - 页面截图
- `evaluate_script` - 执行 JavaScript 代码
- `list_console_messages` - 获取控制台消息

### 网络分析

- `list_network_requests` - 列出网络请求
- `get_network_request` - 获取特定网络请求详情
- `emulate_network` - 模拟网络条件 (3G/4G 等)

### 性能分析

- `performance_start_trace` - 开始性能追踪
- `performance_stop_trace` - 停止性能追踪
- `performance_analyze_insight` - 分析性能洞察
- `emulate_cpu` - 模拟 CPU 节流

### 对话框处理

- `handle_dialog` - 处理浏览器对话框

## 演示运行结果

最新运行结果显示：

## 界面化演示特色功能

### 智能体协作架构

界面化演示采用了先进的多智能体协作架构：

```
Master Agent (主控智能体)
├── Chrome DevTools Agent (浏览器自动化智能体)
│   └── 26个 Chrome DevTools 工具
└── File Agent (文件操作智能体)
    └── 文件系统操作工具
```

### 支持的复杂任务示例

通过 Web 界面，你可以用自然语言描述复杂的自动化任务：

1. **网页数据采集**

   ```
   "访问新闻网站，提取今天的头条新闻标题和链接，保存到CSV文件"
   ```

2. **表单自动化**

   ```
   "打开登录页面，自动填写表单并提交，然后截图保存结果"
   ```

3. **性能分析**

   ```
   "访问目标网站，开始性能追踪，模拟慢速网络条件，分析加载时间"
   ```

4. **批量操作**
   ```
   "依次访问列表中的网站，对每个网站截图并保存页面源码"
   ```

### Web 界面优势

- 📱 **响应式设计**: 支持桌面和移动设备
- 🔄 **实时反馈**: 显示任务执行进度和结果
- 📊 **可视化结果**: 直接在界面中查看截图和数据
- 🎛️ **参数调整**: 可以调整任务参数和配置
- 📝 **历史记录**: 保存和回顾之前的任务执行

```
🚀 启动 Chrome DevTools MCP 简化演示
==================================
📦 检查 Chrome DevTools MCP...
✅ Chrome DevTools MCP 可用
🎬 启动演示...

🔧 演示：列出可用工具
发现 26 个可用工具

🌐 演示：基本浏览器操作
1. 列出当前页面... ✅
2. 创建新页面... ✅
3. 获取页面快照... ✅

📸 演示：页面截图
页面截图成功 ✅

🎉 Chrome DevTools MCP 演示完成！
```

## 系统要求

- **Python 3.7+**
- **Node.js** (用于 npx)
- **Chrome 浏览器**

## 安装依赖

演示脚本会自动检查并安装必要的依赖：

```bash
# Chrome DevTools MCP 会自动安装
npm install -g chrome-devtools-mcp@latest
```

## 使用场景

Chrome DevTools MCP 适用于以下场景：

1. **网页自动化测试**
2. **网页内容抓取**
3. **性能监控和分析**
4. **UI 自动化操作**
5. **网页截图和快照**
6. **表单自动填写**
7. **网络请求分析**

## 注意事项

1. 首次运行时会自动启动 Chrome 浏览器实例
2. 浏览器数据存储在 `~/.cache/chrome-devtools-mcp/chrome-profile`
3. 使用 `--isolated` 参数可以运行多个独立的浏览器实例
4. 演示完成后会自动清理和关闭浏览器进程

## 故障排除

### 常见问题

1. **"npx 命令未找到"**

   - 安装 Node.js: https://nodejs.org/

2. **"Chrome DevTools MCP 不可用"**

   - 运行: `npm install -g chrome-devtools-mcp@latest`

3. **"Python 模块导入错误"**
   - 使用简化演示版本 (`simple_chrome_demo.py`)

### 获取帮助

如果遇到问题，可以：

1. 查看演示脚本的日志输出
2. 检查 Chrome 浏览器是否正常运行
3. 确认网络连接正常

## 扩展开发

基于这些演示，你可以开发自己的浏览器自动化应用：

```python
# 示例：自动化网页操作
async def my_automation():
    # 启动 MCP 服务器
    demo = SimpleChromeDevToolsDemo()
    await demo.start_mcp_server()

    # 创建新页面
    await demo.send_mcp_request("tools/call", {
        "name": "new_page",
        "arguments": {"url": "https://example.com"}
    })

    # 获取页面快照
    snapshot = await demo.send_mcp_request("tools/call", {
        "name": "take_snapshot",
        "arguments": {}
    })

    # 清理
    await demo.stop_mcp_server()
```

---

**祝你使用愉快！** 🚀
