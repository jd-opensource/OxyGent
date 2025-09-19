# OxyGent 本地运行环境准备指南

## 📋 环境检查结果

### ✅ 已具备的环境
- **Python**: 3.9.6 (位置: /usr/bin/python3)
- **Node.js**: v24.7.0 ✅
- **NPX**: 11.5.1 ✅

### ❌ 需要安装的组件
- **UV 包管理器**: 未安装
- **Python 依赖包**: 需要安装
- **pip 版本**: 需要升级 (当前 21.2.4 → 推荐 25.2)

## 🚀 完整设置步骤

### 第一步: 升级 Python 环境
```bash
# 1. 升级 pip
python3 -m pip install --upgrade pip

# 2. 安装 UV 包管理器 (推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc  # 重新加载环境变量
```

### 第二步: 创建虚拟环境
**方法 1: 使用 UV (推荐)**
```bash
uv python install 3.10
uv venv .venv --python 3.10
source .venv/bin/activate
```

**方法 2: 使用 conda**
```bash
conda create -n oxy_env python==3.10
conda activate oxy_env
```

**方法 3: 使用 venv**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 第三步: 安装项目依赖
**方法 1: 使用 UV (推荐)**
```bash
uv pip install -r requirements.txt
```

**方法 2: 使用 pip**
```bash
pip3 install -r requirements.txt
```

**方法 3: 安装发布版本**
```bash
pip3 install oxygent
```

### 第四步: 配置环境变量

#### 🧠 **推荐: 使用浏览器交互模型**
```bash
# 方法 1: 环境变量设置
export DEFAULT_LLM_API_KEY="your-moonshot-api-key"
export DEFAULT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export DEFAULT_LLM_MODEL_NAME="moonshot-v1-128k"

# 方法 2: 创建 .env 文件
cat > .env << EOF
DEFAULT_LLM_API_KEY="your-moonshot-api-key"
DEFAULT_LLM_BASE_URL="https://api.moonshot.cn/v1"
DEFAULT_LLM_MODEL_NAME="moonshot-v1-128k"
EOF
```

#### 🤖 **或者使用 OpenAI**
```bash
# OpenAI 配置
export DEFAULT_LLM_API_KEY="sk-your-openai-key"
export DEFAULT_LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM_MODEL_NAME="gpt-3.5-turbo"
```

#### 🔧 **其他兼容的 API**
```bash
# 其他 OpenAI 兼容的 API
export DEFAULT_LLM_API_KEY="your-api-key"
export DEFAULT_LLM_BASE_URL="your-api-endpoint"
export DEFAULT_LLM_MODEL_NAME="your-model-name"
```

### 第五步: 测试安装
```bash
# 测试环境配置
python3 test_environment.py

# 测试基础功能
python3 demo.py

# 测试浏览器交互功能
python3 examples/advanced/browser_interaction_demo.py

# 测试单个代理
python3 -m examples.agents.single_demo

# 运行单元测试
pytest test/unittest

# 代码格式化
ruff format .
```

## 📦 核心依赖包列表

### Python 依赖 (requirements.txt)
```
aioredis==2.0.1          # Redis 异步客户端
fastapi==0.115.12        # Web API 框架
httpx==0.28.1            # HTTP 客户端
mcp==1.12.3              # Model Context Protocol
numpy==1.26.4            # 数值计算
openai==1.77.0           # OpenAI API
pandas==2.2.3            # 数据处理
pydantic==2.11.4         # 数据验证
uvicorn==0.34.2          # ASGI 服务器
websockets==15.0.1       # WebSocket 支持
elasticsearch[async]==7.13.0  # 搜索引擎
pillow==11.2.1           # 图像处理
```

### Node.js 依赖 (MCP 服务器)
```bash
# 时间服务器
npx mcp-server-time

# 文件系统服务器
npx @modelcontextprotocol/server-filesystem

# 其他 MCP 服务器根据需要安装
```

## 🔧 可选组件

### 数据库服务 (可选)
- **Elasticsearch**: 用于日志和搜索
- **Redis**: 用于缓存和会话管理
- **Vearch**: 用于向量数据库

### 开发工具 (可选)
```bash
# 测试框架
pip3 install pytest pytest-asyncio

# 代码格式化
pip3 install ruff docformatter

# macOS 工具 (可能需要)
brew install coreutils
```

## 🎯 快速验证脚本

创建测试脚本验证环境：

```python
# test_environment.py
import asyncio
import sys

async def test_basic_import():
    try:
        from oxygent import MAS, Config, oxy
        print("✅ OxyGent 导入成功")
        return True
    except ImportError as e:
        print(f"❌ OxyGent 导入失败: {e}")
        return False

async def test_dependencies():
    missing = []
    try:
        import fastapi
        print("✅ FastAPI 可用")
    except ImportError:
        missing.append("fastapi")
    
    try:
        import uvicorn
        print("✅ Uvicorn 可用")
    except ImportError:
        missing.append("uvicorn")
    
    try:
        import mcp
        print("✅ MCP 可用")
    except ImportError:
        missing.append("mcp")
    
    if missing:
        print(f"❌ 缺少依赖: {', '.join(missing)}")
        return False
    return True

async def main():
    print("🔍 检查 OxyGent 运行环境...")
    print(f"Python 版本: {sys.version}")
    
    basic_ok = await test_basic_import()
    deps_ok = await test_dependencies()
    
    if basic_ok and deps_ok:
        print("\n🎉 环境检查通过！可以运行 OxyGent")
    else:
        print("\n❌ 环境检查失败，请按照指南安装缺少的组件")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🚨 常见问题解决

### 1. Python 版本问题
- **当前**: Python 3.9.6
- **推荐**: Python 3.10+
- **解决**: 使用 UV 或 conda 安装 Python 3.10

### 2. MCP 依赖问题
```bash
# 如果 mcp 包安装失败
pip3 install --upgrade pip
pip3 install mcp==1.12.3
```

### 3. Node.js MCP 服务器问题
```bash
# 确保 Node.js 版本 >= 18
node --version

# 全局安装 MCP 服务器
npm install -g @modelcontextprotocol/server-filesystem
```

### 4. 权限问题 (macOS)
```bash
# 如果遇到权限问题
sudo chown -R $(whoami) /usr/local/lib/node_modules
```

## 📚 下一步

1. **完成环境设置** → 运行 `python3 test_environment.py`
2. **配置 LLM** → 设置 API 密钥和端点
3. **运行示例** → `python3 demo.py`
4. **开发自定义功能** → 参考 examples/ 目录

---

*本指南基于当前系统环境 (macOS, Python 3.9.6, Node.js v24.7.0) 生成*
