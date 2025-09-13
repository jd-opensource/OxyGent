# 浏览器自动化工具

OxyGent 提供了强大的浏览器自动化工具集，基于 Playwright 实现，支持网页导航、内容提取、截图、表单填写等功能。

## 安装依赖

使用浏览器自动化工具前，需要安装 Playwright：

```bash
pip install playwright
playwright install
```

## 功能概览

浏览器自动化工具包含以下功能：

1. **网页导航** - 访问指定URL并获取页面信息
2. **内容提取** - 从网页中提取文本内容
3. **截图功能** - 对网页进行截图保存
4. **链接提取** - 获取页面中的所有链接
5. **表单填写** - 自动填写和提交网页表单

## 工具详细说明

### 1. navigate_to_url - 网页导航

导航到指定URL并返回页面基本信息。

**参数：**
- `url` (str): 要访问的URL（必须包含 http:// 或 https://）

**返回：**
```json
{
    "status": "success",
    "title": "页面标题",
    "url": "实际访问的URL",
    "message": "导航成功消息"
}
```

**使用示例：**
```python
from oxygent import preset_tools

# 在智能体中使用
response = await agent.execute("Navigate to https://example.com")
```

### 2. extract_page_content - 内容提取

从网页中提取指定元素的文本内容。

**参数：**
- `url` (str): 要提取内容的URL
- `selector` (str): CSS选择器，默认为 "body"
- `max_length` (int): 提取内容的最大长度，默认为 5000

**返回：**
```json
{
    "status": "success",
    "url": "访问的URL",
    "selector": "使用的CSS选择器",
    "content": "提取的内容",
    "length": 内容长度
}
```

**使用示例：**
```python
# 提取页面标题
response = await agent.execute("Extract the title from https://example.com using selector 'h1'")

# 提取整个页面内容
response = await agent.execute("Get all text content from https://example.com")
```

### 3. take_screenshot - 网页截图

对指定网页进行截图并保存到本地。

**参数：**
- `url` (str): 要截图的URL
- `output_path` (str): 保存截图的路径，默认为 "screenshot.png"
- `full_page` (bool): 是否截取整个页面，默认为 False（仅截取可视区域）

**返回：**
```json
{
    "status": "success",
    "url": "截图的URL",
    "screenshot_path": "截图保存路径",
    "full_page": false,
    "message": "截图成功消息"
}
```

**使用示例：**
```python
# 截取可视区域
response = await agent.execute("Take a screenshot of https://example.com and save as 'example.png'")

# 截取整个页面
response = await agent.execute("Take a full page screenshot of https://example.com")
```

### 4. get_page_links - 链接提取

获取网页中的所有链接信息。

**参数：**
- `url` (str): 要提取链接的URL
- `filter_domain` (bool): 是否只返回同域名的链接，默认为 True
- `max_links` (int): 返回链接的最大数量，默认为 50

**返回：**
```json
{
    "status": "success",
    "url": "访问的URL",
    "total_links": 链接总数,
    "filter_domain": true,
    "links": [
        {
            "text": "链接文本",
            "href": "链接地址",
            "title": "链接标题"
        }
    ]
}
```

**使用示例：**
```python
# 获取页面所有链接
response = await agent.execute("Get all links from https://example.com")

# 获取包括外部链接的所有链接
response = await agent.execute("Get all links from https://example.com including external links")
```

### 5. fill_form - 表单填写

自动填写网页表单并可选择性提交。

**参数：**
- `url` (str): 包含表单的网页URL
- `form_data` (str): JSON格式的表单数据（选择器:值 的键值对）
- `submit` (bool): 是否提交表单，默认为 False
- `submit_selector` (str): 提交按钮的CSS选择器

**表单数据格式：**
```json
{
    "input[name='username']": "用户名",
    "input[name='email']": "email@example.com",
    "textarea[name='message']": "消息内容"
}
```

**返回：**
```json
{
    "status": "success",
    "url": "表单页面URL",
    "filled_fields": [
        {
            "selector": "input[name='username']",
            "value": "用户名",
            "status": "success"
        }
    ],
    "submitted": false,
    "message": "操作结果消息"
}
```

**使用示例：**
```python
# 填写表单但不提交
form_data = '{"input[name=\'username\']": "testuser", "input[name=\'email\']": "test@example.com"}'
response = await agent.execute(f"Fill the form at https://example.com/form with data: {form_data}")

# 填写并提交表单
response = await agent.execute(f"Fill and submit the form at https://example.com/form with data: {form_data}")
```

## 完整使用示例

```python
import asyncio
import os
from oxygent import MAS, Config, oxy, preset_tools

async def browser_demo():
    Config.set_agent_llm_model("default_llm")
    
    oxy_space = [
        oxy.HttpLLM(
            name="default_llm",
            api_key=os.getenv("DEFAULT_LLM_API_KEY"),
            base_url=os.getenv("DEFAULT_LLM_BASE_URL"),
            model_name=os.getenv("DEFAULT_LLM_MODEL_NAME"),
        ),
        
        # 添加浏览器自动化工具
        preset_tools.browser_automation_tools,
        
        oxy.ReActAgent(
            name="browser_agent",
            desc="具备网页浏览和自动化能力的智能体",
            tools=["browser_automation_tools"],
        ),
        
        oxy.ReActAgent(
            is_master=True,
            name="master_agent",
            sub_agents=["browser_agent"],
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        # 执行浏览器任务
        tasks = [
            "Navigate to https://httpbin.org and tell me the page title",
            "Take a screenshot of https://httpbin.org",
            "Get all links from https://httpbin.org",
            "Extract the main content from https://httpbin.org"
        ]
        
        for task in tasks:
            print(f"执行任务: {task}")
            response = await mas.execute(task)
            print(f"结果: {response.output}\n")

if __name__ == "__main__":
    asyncio.run(browser_demo())
```

## 错误处理

所有浏览器工具都包含完善的错误处理机制：

1. **网络错误** - 当无法访问URL时返回详细错误信息
2. **超时错误** - 30秒超时保护，避免长时间等待
3. **元素不存在** - 当CSS选择器找不到元素时给出警告
4. **权限错误** - 处理需要特殊权限的网站访问

## 性能优化

- **浏览器复用** - 使用全局浏览器上下文，减少启动开销
- **无头模式** - 默认使用无头浏览器，提高执行效率
- **内容限制** - 自动限制提取内容长度，避免内存溢出
- **资源清理** - 自动关闭页面和清理资源

## 注意事项

1. **安全性** - 请谨慎使用表单填写功能，避免泄露敏感信息
2. **网站政策** - 遵守目标网站的robots.txt和使用条款
3. **频率限制** - 避免过于频繁的请求，以免被网站封禁
4. **资源管理** - 长时间运行时注意清理浏览器资源

## 扩展开发

如需添加更多浏览器自动化功能，可以参考现有工具的实现方式：

```python
@browser_automation_tools.tool("你的工具描述")
async def your_custom_tool(
    url: str = Field(description="URL参数描述"),
    # 其他参数...
) -> str:
    """你的工具实现"""
    try:
        context = await _get_browser_context()
        page = await context.new_page()
        
        # 你的逻辑实现
        
        await page.close()
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        # 错误处理
        return json.dumps(error_result, ensure_ascii=False, indent=2)
```
