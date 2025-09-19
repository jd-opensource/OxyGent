# Docker 部署文件目录

本目录包含 OxyGent 项目的所有 Docker 相关文件和配置。

## 📁 文件结构

```
docker/
├── README.md                      # 详细的 Docker 部署指南
├── INDEX.md                       # 本文件 - 目录概览
├── env.example                    # 环境变量配置模板
├── docker-compose.yml             # 基础单服务部署
├── docker-compose.ecommerce.yml   # 电商微服务示例部署
└── docker-compose.distributed.yml # 分布式计算示例部署
```

## 🚀 快速开始

1. **复制环境配置**:
   ```bash
   cp docker/env.example .env
   # 编辑 .env 文件，填入您的 LLM API 配置
   ```

2. **选择部署模式**:
   ```bash
   # 基础部署
   ./docker-start.sh
   
   # 电商微服务示例
   ./docker-start.sh ecommerce
   
   # 分布式计算示例
   ./docker-start.sh distributed
   ```

3. **访问服务**:
   - Web 界面: http://localhost:8080/web/index.html
   - API 文档: http://localhost:8080/docs

## 📖 详细文档

请查看 [README.md](./README.md) 获取完整的部署指南，包括：
- 详细的配置选项
- 故障排除指南
- 生产环境部署建议
- 监控和日志管理

## 🛠️ 部署模式

### 基础模式 (`docker-compose.yml`)
- 单个 OxyGent 服务
- Redis 缓存
- Elasticsearch 日志存储
- 可选的本地 Ollama LLM

### 电商示例 (`docker-compose.ecommerce.yml`)
- 网关服务 (8085)
- 产品服务 (8080)
- 订单服务 (8081)
- 支付服务 (8082)
- 物流服务 (8083)
- 共享的 Redis 和 Elasticsearch

### 分布式计算 (`docker-compose.distributed.yml`)
- 主控制器 (8080)
- 数学计算服务 (8081)
- 时间服务 (8082)
- 可选的本地 Ollama LLM

## ⚙️ 配置文件

- **env.example**: 环境变量模板，包含所有必需和可选的配置项
- **各 docker-compose 文件**: 预配置的服务编排，包含健康检查、数据持久化等

## 🔧 管理脚本

位于项目根目录的管理脚本：
- `docker-start.sh`: 启动服务的便捷脚本
- `docker-stop.sh`: 停止和清理服务的脚本

这些脚本会自动处理环境检查、服务依赖、健康检查等操作。
