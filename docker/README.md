# OxyGent Docker 部署指南

OxyGent 的 Docker 部署方案让您能够快速启动和体验多智能体系统，无需复杂的环境配置。

## 🚀 快速开始

### 前提条件
- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 可用内存

### 三步启动

1. **复制环境配置**
   ```bash
   cp docker/env.example .env
   ```

2. **配置 LLM 服务**
   编辑 `.env` 文件，选择以下方式之一：

   **方式一: OpenAI API (推荐)**
   ```bash
   DEFAULT_LLM_API_KEY=your_openai_api_key_here
   DEFAULT_LLM_BASE_URL=https://api.openai.com/v1
   DEFAULT_LLM_MODEL_NAME=gpt-3.5-turbo
   ```

   **方式二: 本地 Ollama (无需 API 密钥)**
   ```bash
   # 无需修改 .env，直接使用 --ollama 参数启动
   ```

3. **启动服务**
   ```bash
   # 使用 API 方式
   ./docker-start.sh

   # 或使用本地 Ollama
   ./docker-start.sh --ollama
   ```

### 访问服务

启动成功后，访问以下地址：

- **🌐 Web 界面**: http://localhost:8080/web/index.html
- **📚 API 文档**: http://localhost:8080/docs
- **❤️ 健康检查**: http://localhost:8080/health

## 📋 常用命令

```bash
# 启动服务
./docker-start.sh                # 使用 API
./docker-start.sh --ollama        # 使用本地 Ollama
./docker-start.sh --logs          # 启动并显示日志

# 停止服务
./docker-stop.sh                  # 停止服务
./docker-stop.sh --cleanup        # 停止并清理资源

# 查看状态
./docker-stop.sh --status         # 查看运行状态
docker-compose -f docker/docker-compose.yml ps  # 查看服务详情

# 查看日志
docker-compose -f docker/docker-compose.yml logs -f
```

## ⚙️ 配置说明

### 服务组件

| 服务 | 端口 | 描述 |
|------|------|------|
| OxyGent | 8080 | 主应用服务 |
| Redis | 6379 | 缓存服务 |
| Elasticsearch | 9200 | 日志存储 |
| Ollama | 11434 | 本地 LLM (可选) |

### 数据持久化

数据存储在以下 Docker 卷中：
- `redis_data`: Redis 数据
- `elasticsearch_data`: 日志数据  
- `ollama_data`: Ollama 模型数据
- `./cache_dir`: 应用缓存
- `./local_file`: 本地文件

## 🛠️ 故障排除

### 常见问题

1. **启动失败**
   ```bash
   # 查看详细日志
   ./docker-start.sh --logs
   
   # 检查端口占用
   lsof -i :8080
   ```

2. **LLM 连接失败**
   - 检查 `.env` 文件中的 API 密钥
   - 确认网络连接正常
   - 尝试使用本地 Ollama: `./docker-start.sh --ollama`

3. **内存不足**
   ```bash
   # 检查系统资源
   docker system df
   
   # 清理未使用资源
   docker system prune
   ```

4. **服务无响应**
   ```bash
   # 重启服务
   ./docker-stop.sh
   ./docker-start.sh
   
   # 检查健康状态
   curl http://localhost:8080/health
   ```

### 重置和清理

```bash
# 完全重置 (⚠️ 会丢失所有数据)
./docker-stop.sh --cleanup

# 重新构建镜像
./docker-start.sh --build
```

## 🔧 高级配置

### 自定义配置

如需修改默认配置，可编辑 `docker/docker-compose.yml` 文件：

- **端口映射**: 修改 `ports` 部分
- **内存限制**: 添加 `deploy.resources` 配置
- **环境变量**: 修改 `environment` 部分

### 生产环境

生产环境建议：

1. **使用外部数据库**
2. **配置 HTTPS**
3. **设置资源限制**
4. **配置监控告警**
5. **定期备份数据**

## 💡 使用技巧

### 本地开发

```bash
# 开发模式 (实时查看日志)
./docker-start.sh --logs

# 修改代码后重新构建
./docker-start.sh --build
```

### 性能调优

- **内存**: 确保至少 2GB 可用内存
- **存储**: SSD 硬盘可提升性能
- **网络**: 良好的网络连接对 API 调用很重要

### 数据管理

```bash
# 备份重要数据
docker cp oxygent_oxygent_1:/app/cache_dir ./backup_cache
docker cp oxygent_oxygent_1:/app/local_file ./backup_files

# 查看数据使用情况
docker system df -v
```

## 📞 获取帮助

遇到问题时：

1. 查看 [常见问题](#常见问题) 部分
2. 检查项目 [Issues](https://github.com/jd-opensource/OxyGent/issues)
3. 提交新 Issue 时请包含：
   - 错误日志
   - 环境信息
   - 复现步骤

## 🎯 下一步

成功启动后，您可以：

1. **探索 Web 界面** - 体验多智能体对话
2. **查看 API 文档** - 了解编程接口
3. **阅读项目文档** - 深入学习 OxyGent
4. **尝试自定义** - 添加您自己的智能体

---

**快速体验 OxyGent 的强大功能，开启您的多智能体之旅！** 🚀