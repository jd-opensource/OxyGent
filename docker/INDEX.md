# Docker 部署文件目录

本目录包含 OxyGent 项目的 Docker 部署文件和配置，专注于快速入门体验。

## 📁 文件结构

```
docker/
├── README.md          # 详细的 Docker 部署指南
├── INDEX.md           # 本文件 - 目录概览
├── env.example        # 环境变量配置模板
└── docker-compose.yml # Docker 服务编排配置
```

## 🚀 三步快速开始

1. **复制环境配置**:
   ```bash
   cp docker/env.example .env
   # 编辑 .env 文件，填入您的 LLM API 配置
   ```

2. **启动服务**:
   ```bash
   # 使用 API 方式 (需要 API 密钥)
   ./docker-start.sh
   
   # 或使用本地 Ollama (无需 API 密钥)
   ./docker-start.sh --ollama
   ```

3. **访问服务**:
   - 🌐 Web 界面: http://localhost:8080/web/index.html
   - 📚 API 文档: http://localhost:8080/docs

## 📖 详细文档

请查看 [README.md](./README.md) 获取完整的部署指南，包括：
- 详细的配置选项
- 故障排除指南
- 常用命令参考
- 高级配置说明

## 🛠️ 服务组件

OxyGent Docker 部署包含以下服务：

- **OxyGent** (8080): 主应用服务，提供多智能体功能
- **Redis** (6379): 缓存服务，提升性能
- **Elasticsearch** (9200): 日志存储，便于调试
- **Ollama** (11434): 本地 LLM 服务 (可选)

## ⚙️ 配置文件

- **env.example**: 环境变量模板，包含 LLM 配置选项
- **docker-compose.yml**: 服务编排配置，包含健康检查、数据持久化等

## 🔧 管理脚本

位于项目根目录的便捷脚本：

- `docker-start.sh`: 一键启动 OxyGent 服务
  - `--ollama`: 使用本地 Ollama LLM
  - `--logs`: 启动后显示日志
  - `--build`: 重新构建镜像

- `docker-stop.sh`: 停止和清理服务
  - `--cleanup`: 完全清理资源
  - `--status`: 查看运行状态

## 💡 设计理念

这个基础部署方案专注于：

- **🚀 快速体验** - 最少配置，快速启动
- **🔧 简单易用** - 清晰的文档和便捷脚本
- **💪 功能完整** - 包含完整的 OxyGent 核心功能
- **🛠️ 易于调试** - 完善的日志和健康检查

让您能够在几分钟内体验 OxyGent 的强大多智能体功能！
