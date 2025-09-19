# Docker 部署文件目录

本目录包含 OxyGent 的完整 Docker 部署方案。

## 📁 文件结构

```
docker/
├── README.md              # 详细部署指南
├── INDEX.md              # 本文件 - 目录说明
├── docker-compose.yml    # Docker Compose 配置
├── env.example          # 环境变量模板
├── cache_dir/           # 应用缓存目录（自动创建）
└── local_file/          # 本地文件目录（自动创建）
```

## 🚀 快速开始

1. **复制环境变量模板**:
   ```bash
   cp docker/env.example .env
   ```

2. **编辑环境变量**:
   ```bash
   # 填入您的 LLM API 配置
   vim .env
   ```

3. **启动服务**:
   ```bash
   # 在 docker 目录中启动
   cd docker && ./docker-start.sh
   
   # 使用本地 Ollama
   cd docker && ./docker-start.sh --ollama
   
   # 或在根目录使用快捷方式
   ./docker-start.sh
   ```

4. **访问服务**:
   - Web 界面: http://localhost:8080/web/index.html
   - API 文档: http://localhost:8080/docs

## 📖 详细文档

请参阅 [README.md](./README.md) 获取完整的部署指南和故障排除信息。

## ⚡ 一键命令

```bash
# 完整部署流程
cp docker/env.example .env && \
echo "请编辑 .env 文件填入 API 密钥，然后运行: cd docker && ./docker-start.sh" && \
vim .env
```