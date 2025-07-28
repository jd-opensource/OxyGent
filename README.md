# OxyGent Gaia

![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![GAIA Benchmark](https://img.shields.io/badge/GAIA%20Score-59.14%25-green)

Open-Source Multi-Agent Framework for Real-World Task Automation

## 🧠 Introduction

OxyGent Gaia is a specialized branch of the OxyGent framework optimized for the GAIA Benchmark—a comprehensive evaluation of real-world task automation capabilities. This implementation achieves 59.14% accuracy on GAIA, demonstrating state-of-the-art performance among open-source multi-agent frameworks.

Built upon OxyGent's core architecture, Gaia implements hierarchical multi-agent processing with patented Oxy-Atomic Operators™ for dynamic task decomposition and execution.

## ⚙️ Installation

```bash
# Create Python environment
conda create -n oxygent_gaia python=3.12
conda activate oxygent_gaia

# Install core dependencies
pip install oxygent 
pip install camelot-py==1.0.0
pip install -r requirements.txt

# Configure browser automation
playwright install chromium --with-deps --no-shell
```

## 🔑 Configuration

1. Configure API keys in `.env`:
```env
# Core AI Services
MODEL_GPT4O = "your_openai_key"
MODEL_CLAUDE = "your_anthropic_key"
MODEL_DEEPSEEK_V3 = "your_deepseek_key"

# Tooling Services
GITHUB_TOKEN = "your_github_pat"
YT_API_KEY = "your_youtube_api_key"
HF_TOKEN = "your_huggingface_token"

# System Paths
CACHE_DIR = "/path/to/cache"
OUTPUT_DIR = "/path/to/results"
```

## 🚀 Usage

Run full GAIA benchmark evaluation:
```bash
python examples/gaia/run_gaia.py
```

For specific test cases, use:
```bash
python examples/gaia/gaia_single.py
```
