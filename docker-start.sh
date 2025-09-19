#!/bin/bash

# OxyGent Docker 快速启动脚本
# 使用方法: ./docker-start.sh [options]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# 显示帮助信息
show_help() {
    cat << EOF
OxyGent Docker 快速启动脚本

使用方法:
    $0 [OPTIONS]

选项:
    --ollama        使用本地 Ollama LLM 服务 (无需 API 密钥)
    --build         强制重新构建镜像
    --logs          启动后显示日志
    --help          显示此帮助信息

示例:
    $0                              # 基础部署 (需要 LLM API 密钥)
    $0 --ollama                     # 使用本地 Ollama (无需 API 密钥)
    $0 --build --logs               # 重构建 + 显示日志
    $0 --ollama --logs              # Ollama + 显示日志

环境变量配置:
    cp docker/env.example .env      # 复制环境变量模板
    # 编辑 .env 文件，填入您的 LLM API 配置

EOF
}

# 检查 Docker 环境
check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        error "Docker 服务未运行，请启动 Docker"
        exit 1
    fi

    log "Docker 环境检查通过"
}

# 检查环境变量
check_env() {
    if [[ ! -f ".env" ]]; then
        warn ".env 文件不存在，将使用默认配置"
        if [[ -f "./docker/env.example" ]]; then
            cp ./docker/env.example .env
            info "已从 ./docker/env.example 创建 .env 文件，请编辑后重新运行"
        else
            cat > .env << EOF
# LLM 配置
DEFAULT_LLM_API_KEY=your_api_key_here
DEFAULT_LLM_BASE_URL=http://host.docker.internal:11434
DEFAULT_LLM_MODEL_NAME=llama2

# 应用环境
APP_ENV=docker
EOF
        fi
        info "已创建示例 .env 文件，请编辑后重新运行"
        exit 0
    fi

    # 检查必需的环境变量
    source .env
    if [[ -z "$DEFAULT_LLM_API_KEY" ]] || [[ "$DEFAULT_LLM_API_KEY" == "your_api_key_here" ]]; then
        warn "请在 .env 文件中配置有效的 DEFAULT_LLM_API_KEY"
    fi

    log "环境变量检查完成"
}

# 创建必要的目录
create_directories() {
    mkdir -p cache_dir local_file
    log "创建必要的目录"
}

# 启动服务
start_services() {
    local compose_file="./docker/docker-compose.yml"
    local profiles=""
    local build_flag=""
    local logs_flag=false

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ollama)
                profiles="--profile ollama"
                shift
                ;;
            --build)
                build_flag="--build"
                shift
                ;;
            --logs)
                logs_flag=true
                shift
                ;;
            *)
                warn "未知参数: $1"
                shift
                ;;
        esac
    done

    log "启动 OxyGent 服务"
    if [[ -n "$profiles" ]]; then
        info "包含本地 Ollama LLM 服务"
    fi

    if [[ ! -f "$compose_file" ]]; then
        error "Compose 文件不存在: $compose_file"
        exit 1
    fi

    # 构建命令
    local cmd="docker-compose -f $compose_file $profiles up -d $build_flag"
    
    log "启动服务: $cmd"
    eval $cmd

    # 等待服务启动
    log "等待服务启动..."
    sleep 10

    # 检查服务状态
    info "服务状态:"
    docker-compose -f $compose_file ps

    # 显示访问信息
    show_access_info

    # 显示日志
    if [[ "$logs_flag" == true ]]; then
        log "显示服务日志 (Ctrl+C 退出):"
        docker-compose -f $compose_file logs -f
    fi
}

# 显示访问信息
show_access_info() {
    echo
    info "🎉 OxyGent 启动成功！"
    echo
    
    info "服务访问地址:"
    info "  🌐 Web 界面: http://localhost:8080/web/index.html"
    info "  📚 API 文档: http://localhost:8080/docs"
    info "  ❤️  健康检查: http://localhost:8080/health"
    
    echo
    info "支持服务:"
    info "  📊 Redis: localhost:6379"
    info "  🔍 Elasticsearch: http://localhost:9200"
    if docker-compose -f "./docker/docker-compose.yml" ps | grep -q ollama; then
        info "  🤖 Ollama: http://localhost:11434"
    fi
    
    echo
    info "常用命令:"
    info "  📋 查看日志: ./docker-start.sh --logs"
    info "  🛑 停止服务: ./docker-stop.sh"
    info "  🔄 重启服务: docker-compose -f ./docker/docker-compose.yml restart"
    
    echo
    info "💡 提示: 首次启动可能需要几分钟来下载镜像和初始化服务"
    echo
}

# 主函数
main() {
    # 解析参数
    if [[ $# -gt 0 ]]; then
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
        esac
    fi

    log "开始启动 OxyGent Docker 服务..."
    
    check_docker
    check_env
    create_directories
    start_services "$@"
    
    log "启动完成！"
}

# 执行主函数
main "$@"
