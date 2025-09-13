# 浏览器自动化工具集 PR 说明

## 概述

本 PR 为 OxyGent 框架添加了完整的浏览器自动化工具集，基于 Playwright 实现，填补了 OxyGent 相比 OpenManus 等竞争框架在 Web 交互能力方面的空白。

## 🎯 解决的问题

1. **功能缺失**：OxyGent 之前缺少浏览器自动化能力，限制了智能体在现代 Web 环境中的应用
2. **竞争劣势**：相比 OpenManus 等框架，缺少关键的 Web 交互工具
3. **用户需求**：现代智能体系统必须具备网页导航、内容提取、截图等基础能力

## 🚀 新增功能

### 核心工具函数

1. **navigate_to_url** - 网页导航
   - 访问指定 URL 并返回页面基本信息
   - 支持超时控制和错误处理

2. **extract_page_content** - 内容提取  
   - 基于 CSS 选择器提取网页内容
   - 支持内容长度限制和格式化

3. **take_screenshot** - 网页截图
   - 支持全页面或可视区域截图
   - 自动创建输出目录

4. **get_page_links** - 链接提取
   - 提取页面所有链接信息
   - 支持同域过滤和数量限制

5. **fill_form** - 表单自动化
   - 自动填写网页表单
   - 支持可选的表单提交

### 架构特性

- **资源复用**：全局浏览器上下文，减少启动开销
- **错误处理**：完善的异常处理和错误信息返回
- **性能优化**：无头模式运行，30秒超时保护
- **安全考虑**：沙箱模式运行，避免安全风险

## 📁 文件变更

### 新增文件

1. **oxygent/preset_tools/browser_automation_tools.py** - 主要工具实现
2. **test/unittest/test_browser_automation_tools.py** - 单元测试
3. **examples/advanced/browser_automation_demo.py** - 使用示例
4. **docs/docs_zh/browser_automation_tools.md** - 中文文档

### 修改文件

1. **requirements.txt** - 添加 `playwright==1.48.0` 依赖
2. **oxygent/preset_tools/__init__.py** - 导入新工具模块

## 🧪 测试覆盖

- ✅ 单元测试覆盖所有核心功能
- ✅ Mock 测试避免真实网络请求
- ✅ 错误场景测试
- ✅ 代码语法验证通过
- ✅ 代码格式化完成

## 📖 使用示例

```python
import asyncio
from oxygent import MAS, Config, oxy, preset_tools

async def main():
    Config.set_agent_llm_model("default_llm")
    
    oxy_space = [
        oxy.HttpLLM(name="default_llm", ...),
        preset_tools.browser_automation_tools,  # 新增工具
        oxy.ReActAgent(
            name="browser_agent",
            tools=["browser_automation_tools"]
        ),
    ]

    async with MAS(oxy_space=oxy_space) as mas:
        # 网页导航
        await mas.execute("Navigate to https://example.com")
        
        # 内容提取  
        await mas.execute("Extract content from https://example.com")
        
        # 截图
        await mas.execute("Take screenshot of https://example.com")

asyncio.run(main())
```

## 🔧 安装要求

使用前需要安装 Playwright：

```bash
pip install playwright
playwright install
```

## 🎨 设计理念

1. **一致性**：遵循 OxyGent 现有工具的设计模式
2. **可扩展性**：模块化设计，易于添加新功能
3. **可靠性**：完善的错误处理和资源管理
4. **易用性**：简单直观的 API 设计

## 🔄 与现有系统集成

- 完全兼容现有的 FunctionHub 架构
- 遵循统一的工具注册和调用机制
- 支持与其他预设工具组合使用
- 可与多智能体系统无缝集成

## 📊 性能考量

- **内存优化**：浏览器上下文复用
- **执行效率**：无头模式运行
- **资源管理**：自动清理页面资源
- **超时保护**：避免长时间阻塞

## 🛡️ 安全特性

- 沙箱环境运行
- 禁用不必要的浏览器功能
- 内容长度限制防止内存溢出
- 路径验证防止目录遍历

## 🔮 未来扩展

本 PR 为第一阶段实现，后续可扩展：

1. **高级交互**：点击、滚动、拖拽等操作
2. **文件处理**：文件上传下载功能  
3. **性能监控**：页面加载时间统计
4. **智能等待**：元素出现等待机制

## 🎯 对比竞争框架

| 功能 | OxyGent (本PR后) | OpenManus | 优势 |
|------|------------------|-----------|------|
| 网页导航 | ✅ | ✅ | 功能对等 |
| 内容提取 | ✅ | ✅ | 更灵活的选择器 |
| 截图功能 | ✅ | ✅ | 支持全页面截图 |
| 表单自动化 | ✅ | ✅ | 更好的错误处理 |
| 企业级特性 | ✅ | ❌ | 更强的可观测性 |

## ✅ 贡献指南遵循

- [x] 选择了 `PR welcome` 标签的功能需求
- [x] 遵循项目代码规范和架构设计
- [x] 提供完整的测试覆盖
- [x] 包含详细的文档说明
- [x] 使用 ruff 和 docformatter 格式化代码

## 🤝 致谢

感谢 OxyGent 社区提供的优秀框架基础，以及 Playwright 团队提供的强大浏览器自动化能力。

---

**此 PR 显著增强了 OxyGent 的 Web 交互能力，使其在智能体框架竞争中更具优势。**
