# OxyGent Gaia

![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![GAIA Benchmark](https://img.shields.io/badge/GAIA%20Score-59.14%25-green)

Open-Source Multi-Agent Framework for Real-World Task Automation

## 🧠 简介

OxyGent Gaia 是 OxyGent 框架的一个专门分支，针对 GAIA 基准测试进行了优化。GAIA 是对现实世界任务自动化能力的全面评估。本实现在 GAIA 上达到了 59.14% 的准确率，展示了开源多智能体框架的先进性能。

基于 OxyGent 的核心架构，Gaia 实现了分层多智能体处理，并采用 Oxy-Atomic Operators 进行动态任务分解和执行。

## ⚙️ 安装

```bash
# 创建 Python 环境
conda create -n oxygent_gaia python=3.12
conda activate oxygent_gaia

# 安装核心依赖
pip install camelot-py==1.0.0
pip install -r requirements.txt
pip install oxygent 
# 配置浏览器自动化
playwright install chromium --with-deps --no-shell
```

## 🔑 配置

1. 在 .env 中配置 API 密钥：
```env
# 核心 AI 服务 
MODEL_GPT4O = "your_openai_key"
MODEL_CLAUDE = "your_anthropic_key"
MODEL_DEEPSEEK_V3 = "your_deepseek_key"

# 工具服务
GITHUB_TOKEN = "your_github_pat"
YT_API_KEY = "your_youtube_api_key"
HF_TOKEN = "your_huggingface_token"

# 系统路径
CACHE_DIR = "/path/to/cache"
OUTPUT_DIR = "/path/to/results"
```

## 🚀 使用

运行完整 GAIA 基准测试评估：
```bash
python examples/gaia/run_gaia.py
```

对于特定测试用例，使用：
```bash
python examples/gaia/gaia_single.py
```
