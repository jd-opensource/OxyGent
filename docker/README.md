# OxyGent Docker 部署指南

本文档提供 OxyGent 的 Docker 容器化部署方案，支持一键启动完整的多智能体系统。

## 🚀 快速开始

### 1. 环境准备

确保您的系统已安装：
- **Docker** (20.10+)
- **Docker Compose** (2.0+)

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp docker/env.example .env

# 编辑 .env 文件，填入您的 LLM API 配置
vim .env
```

### 3. 一键启动

```bash
# 基础启动（需要 LLM API 密钥）
cd docker && ./docker-start.sh

# 使用本地 Ollama（无需 API 密钥）
cd docker && ./docker-start.sh --ollama

# 强制重新构建
cd docker && ./docker-start.sh --build

# 启动并显示日志
cd docker && ./docker-start.sh --logs

# 或者在根目录使用快捷方式
./docker-start.sh
```

### 4. 访问服务

启动成功后，您可以通过以下地址访问：

- **🌐 Web 界面**: http://localhost:8080/web/index.html
- **📚 API 文档**: http://localhost:8080/docs
- **❤️ 健康检查**: http://localhost:8080/health

## 📖 详细配置

### 环境变量配置

在 `.env` 文件中配置以下变量：

```bash
# LLM 服务配置（必需）
DEFAULT_LLM_API_KEY=your_api_key_here
DEFAULT_LLM_BASE_URL=https://api.openai.com/v1
DEFAULT_LLM_MODEL_NAME=gpt-3.5-turbo
```

### 支持的 LLM 服务

#### 1. OpenAI API
```bash
DEFAULT_LLM_API_KEY=sk-xxx
DEFAULT_LLM_BASE_URL=https://api.openai.com/v1
DEFAULT_LLM_MODEL_NAME=gpt-3.5-turbo
```

#### 2. Moonshot Kimi API
```bash
DEFAULT_LLM_API_KEY=sk-xxx
DEFAULT_LLM_BASE_URL=https://api.moonshot.cn/v1
DEFAULT_LLM_MODEL_NAME=moonshot-v1-8k
```

#### 3. 本地 Ollama
```bash
# 启动时使用 --ollama 参数
./docker-start.sh --ollama
```

## 🏗️ 架构说明

### 服务组件

- **oxygent**: 主应用服务 (端口 8080)
- **redis**: 缓存服务 (端口 6379)
- **elasticsearch**: 搜索引擎 (端口 9200)
- **ollama**: 本地 LLM 服务 (端口 11434, 可选)

### 数据持久化

- `redis_data`: Redis 数据卷
- `elasticsearch_data`: Elasticsearch 数据卷
- `ollama_data`: Ollama 模型数据卷
- `./cache_dir`: 应用缓存目录
- `./local_file`: 本地文件目录

## 🔧 管理命令

### 启动服务

```bash
# 基础启动
cd docker && ./docker-start.sh

# 使用 Ollama
cd docker && ./docker-start.sh --ollama

# 重新构建镜像
cd docker && ./docker-start.sh --build

# 显示日志
cd docker && ./docker-start.sh --logs
```

### 停止服务

```bash
# 停止服务
cd docker && ./docker-stop.sh

# 停止并删除数据卷（⚠️ 会丢失数据）
cd docker && ./docker-stop.sh --remove-volumes

# 完全清理
cd docker && ./docker-stop.sh --cleanup
```

### 查看状态

```bash
# 查看服务状态
cd docker && ./docker-stop.sh --status

# 查看日志
cd docker && docker compose -f ./docker-compose.yml logs -f
```

## 🐛 故障排除

### 常见问题

#### 1. API 速率限制错误 (429)

**问题**: `429 Too Many Requests` 错误

**解决方案**:
- 检查您的 API 配额和速率限制
- 使用较小的模型（如 `moonshot-v1-8k` 而不是 `moonshot-v1-128k`）
- 等待速率限制重置后重试
- 考虑使用本地 Ollama: `./docker-start.sh --ollama`

#### 2. 环境变量未生效

**问题**: 容器内环境变量为空

**解决方案**:
```bash
# 确保 .env 文件在项目根目录
ls -la .env

# 重新启动服务
./docker-stop.sh && ./docker-start.sh
```

#### 3. 端口冲突

**问题**: 端口已被占用

**解决方案**:
```bash
# 检查端口占用
lsof -i :8080

# 修改 docker-compose.yml 中的端口映射
```

#### 4. Docker Compose 命令不兼容

**问题**: `docker-compose: command not found`

**解决方案**: 脚本已自动兼容新旧版本的 Docker Compose 命令。

### 查看详细日志

```bash
# 查看所有服务日志
cd docker && docker compose -f ./docker-compose.yml logs

# 查看特定服务日志
cd docker && docker compose -f ./docker-compose.yml logs oxygent

# 实时日志
cd docker && docker compose -f ./docker-compose.yml logs -f
```

## 🔒 安全注意事项

1. **API 密钥安全**: `.env` 文件包含敏感信息，不要提交到版本控制系统
2. **网络安全**: 生产环境中请配置防火墙和访问控制
3. **数据备份**: 定期备份重要数据卷

## 📊 性能优化

### 资源配置

根据您的使用场景调整资源限制：

```yaml
# docker-compose.yml
services:
  oxygent:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

### API 配额管理

对于免费 API 账户：
- 控制请求频率
- 使用较小的模型
- 考虑本地 LLM 方案

## 🤝 贡献

如果您遇到问题或有改进建议，欢迎：
1. 提交 Issue
2. 创建 Pull Request
3. 参与讨论

## 📝 更新日志

- **v1.0.0**: 初始 Docker 部署方案
- 支持多种 LLM 服务
- 自动化启停脚本
- 完整的故障排除指南