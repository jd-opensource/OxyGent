# OxyGent Docker Compose 部署指南

本文档提供了 OxyGent 项目的 Docker Compose 部署方案，支持单服务和分布式多服务部署。

## 📋 前提条件

- Docker 20.10+ 
- Docker Compose 2.0+
- 至少 4GB 可用内存
- 至少 2GB 可用磁盘空间

## 🚀 快速开始

### 1. 环境配置

创建 `.env` 文件配置 LLM 服务：

```bash
# LLM 配置 (必需)
DEFAULT_LLM_API_KEY=your_api_key_here
DEFAULT_LLM_BASE_URL=https://api.openai.com/v1
DEFAULT_LLM_MODEL_NAME=gpt-3.5-turbo

# 或者使用本地 Ollama (可选)
# DEFAULT_LLM_BASE_URL=http://host.docker.internal:11434
# DEFAULT_LLM_MODEL_NAME=llama2
```

### 2. 基础部署

启动单个 OxyGent 服务：

```bash
# 启动所有服务 (包括 Redis, Elasticsearch)
docker-compose up -d

# 仅启动 OxyGent 服务 (不包括数据库)
docker-compose up -d oxygent

# 启动并包含本地 Ollama LLM
docker-compose --profile with-ollama up -d
```

访问服务：
- **Web 界面**: http://localhost:8080/web/index.html
- **API 文档**: http://localhost:8080/docs
- **健康检查**: http://localhost:8080/health

### 3. 分布式电商示例部署

启动完整的电商微服务系统：

```bash
# 启动电商分布式服务
docker-compose -f docker-compose.ecommerce.yml up -d

# 查看服务状态
docker-compose -f docker-compose.ecommerce.yml ps
```

服务端口映射：
- **网关服务**: http://localhost:8085 (主入口)
- **产品服务**: http://localhost:8080
- **订单服务**: http://localhost:8081  
- **支付服务**: http://localhost:8082
- **物流服务**: http://localhost:8083

### 4. 分布式计算示例部署

启动分布式计算服务：

```bash
# 启动分布式计算服务
docker-compose -f docker-compose.distributed.yml up -d

# 包含本地 Ollama
docker-compose -f docker-compose.distributed.yml --profile with-ollama up -d
```

服务端口映射：
- **主控制器**: http://localhost:8080 (主入口)
- **数学计算服务**: http://localhost:8081
- **时间服务**: http://localhost:8082

## 🔧 配置选项

### 环境变量

| 变量名 | 描述 | 默认值 | 必需 |
|--------|------|--------|------|
| `DEFAULT_LLM_API_KEY` | LLM API 密钥 | - | ✅ |
| `DEFAULT_LLM_BASE_URL` | LLM API 基础URL | `http://host.docker.internal:11434` | ✅ |
| `DEFAULT_LLM_MODEL_NAME` | LLM 模型名称 | `llama2` | ✅ |
| `APP_ENV` | 应用环境 | `docker` | ❌ |

### 数据持久化

数据卷配置：
- `redis_data`: Redis 数据存储
- `elasticsearch_data`: Elasticsearch 数据存储  
- `ollama_data`: Ollama 模型存储
- `./cache_dir`: 应用缓存目录
- `./local_file`: 本地文件存储

### 资源限制 (推荐)

在生产环境中，建议添加资源限制：

```yaml
services:
  oxygent:
    # ... 其他配置
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

## 📊 监控和日志

### 健康检查

所有服务都配置了健康检查：

```bash
# 检查所有服务健康状态
docker-compose ps

# 查看特定服务健康状态
docker-compose exec oxygent curl -f http://localhost:8080/health
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f oxygent

# 查看最近100行日志
docker-compose logs --tail=100 oxygent
```

### 性能监控

```bash
# 查看资源使用情况
docker stats

# 查看容器详细信息
docker-compose exec oxygent ps aux
```

## 🛠️ 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 检查日志
   docker-compose logs oxygent
   
   # 重启服务
   docker-compose restart oxygent
   ```

2. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8080
   
   # 修改端口映射
   # 编辑 docker-compose.yml 中的 ports 配置
   ```

3. **内存不足**
   ```bash
   # 检查系统资源
   docker system df
   
   # 清理未使用的资源
   docker system prune -a
   ```

4. **LLM 连接失败**
   - 检查 `.env` 文件中的 LLM 配置
   - 确认 API 密钥有效
   - 检查网络连接

### 调试模式

启用详细日志：

```bash
# 设置调试环境变量
echo "LOG_LEVEL=DEBUG" >> .env

# 重启服务
docker-compose restart oxygent
```

## 🔄 更新和维护

### 更新镜像

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker-compose build --no-cache

# 重启服务
docker-compose up -d
```

### 数据备份

```bash
# 备份 Redis 数据
docker-compose exec redis redis-cli BGSAVE

# 备份 Elasticsearch 数据
docker-compose exec elasticsearch curl -X POST "localhost:9200/_snapshot/backup/snapshot_$(date +%Y%m%d)"
```

### 清理和重置

```bash
# 停止所有服务
docker-compose down

# 删除所有数据 (⚠️ 谨慎操作)
docker-compose down -v

# 清理所有相关资源
docker-compose down -v --remove-orphans
docker system prune -a
```

## 📚 进阶配置

### 自定义配置

1. **修改配置文件**: 编辑 `config.json` 中的 `docker` 环境配置
2. **添加自定义服务**: 在 `docker-compose.yml` 中添加新的服务定义
3. **网络配置**: 自定义 Docker 网络设置

### 生产环境部署

生产环境建议：

1. **使用外部数据库**: 配置外部 Redis/Elasticsearch 集群
2. **负载均衡**: 使用 Nginx 或云负载均衡器
3. **SSL/TLS**: 配置 HTTPS 证书
4. **监控告警**: 集成 Prometheus/Grafana
5. **日志聚合**: 使用 ELK 或云日志服务

### 扩展和自定义

- 添加新的 Agent 服务
- 集成外部工具和数据库
- 自定义 MCP 服务器
- 配置 GPU 加速 (本地 LLM)

## 📞 支持

如遇到问题，请：

1. 查看 [常见问题](#常见问题) 部分
2. 检查项目 [Issues](https://github.com/jd-opensource/OxyGent/issues)
3. 提交新的 Issue 并包含：
   - Docker 版本信息
   - 完整的错误日志
   - 复现步骤

---

**注意**: 这是社区贡献的 Docker 部署方案，如有问题欢迎提交 PR 改进。
