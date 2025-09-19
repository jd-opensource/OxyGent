#!/bin/bash

# Docker Compose 启动脚本 for OxyGent
# 使用方法: ./docker-start.sh [basic|ecommerce|distributed] [options]

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
OxyGent Docker Compose 启动脚本

使用方法:
    $0 [MODE] [OPTIONS]

模式:
    basic           基础单服务部署 (默认)
    ecommerce       电商分布式示例部署
    distributed     分布式计算示例部署

选项:
    --with-ollama   包含本地 Ollama LLM 服务
    --build         强制重新构建镜像
    --logs          启动后显示日志
    --help          显示此帮助信息

示例:
    $0                              # 基础部署
    $0 basic --with-ollama          # 基础部署 + Ollama
    $0 ecommerce --build --logs     # 电商部署 + 重构建 + 显示日志
    $0 distributed                  # 分布式计算部署

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
        cat > .env << EOF
# LLM 配置
DEFAULT_LLM_API_KEY=your_api_key_here
DEFAULT_LLM_BASE_URL=http://host.docker.internal:11434
DEFAULT_LLM_MODEL_NAME=llama2

# 应用环境
APP_ENV=docker
EOF
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
    local mode=$1
    local compose_file="docker-compose.yml"
    local profiles=""
    local build_flag=""
    local logs_flag=false

    # 解析参数
    shift
    while [[ $# -gt 0 ]]; do
        case $1 in
            --with-ollama)
                profiles="--profile with-ollama"
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

    # 选择 compose 文件
    case $mode in
        ecommerce)
            compose_file="docker-compose.ecommerce.yml"
            log "使用电商分布式部署模式"
            ;;
        distributed)
            compose_file="docker-compose.distributed.yml"
            log "使用分布式计算部署模式"
            ;;
        basic|*)
            compose_file="docker-compose.yml"
            log "使用基础部署模式"
            ;;
    esac

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
    show_access_info $mode

    # 显示日志
    if [[ "$logs_flag" == true ]]; then
        log "显示服务日志 (Ctrl+C 退出):"
        docker-compose -f $compose_file logs -f
    fi
}

# 显示访问信息
show_access_info() {
    local mode=$1
    
    echo
    info "🎉 服务启动成功！"
    echo
    
    case $mode in
        ecommerce)
            info "电商系统访问地址:"
            info "  网关服务 (主入口): http://localhost:8085/web/index.html"
            info "  产品服务: http://localhost:8080/web/index.html"
            info "  订单服务: http://localhost:8081/web/index.html"
            info "  支付服务: http://localhost:8082/web/index.html"
            info "  物流服务: http://localhost:8083/web/index.html"
            ;;
        distributed)
            info "分布式计算系统访问地址:"
            info "  主控制器 (主入口): http://localhost:8080/web/index.html"
            info "  数学计算服务: http://localhost:8081/web/index.html"
            info "  时间服务: http://localhost:8082/web/index.html"
            ;;
        *)
            info "OxyGent 服务访问地址:"
            info "  Web 界面: http://localhost:8080/web/index.html"
            info "  API 文档: http://localhost:8080/docs"
            ;;
    esac
    
    echo
    info "其他服务:"
    info "  Redis: localhost:6379"
    info "  Elasticsearch: http://localhost:9200"
    if docker-compose ps | grep -q ollama; then
        info "  Ollama: http://localhost:11434"
    fi
    
    echo
    info "常用命令:"
    info "  查看日志: docker-compose -f $compose_file logs -f"
    info "  停止服务: docker-compose -f $compose_file down"
    info "  重启服务: docker-compose -f $compose_file restart"
    echo
}

# 主函数
main() {
    local mode="basic"
    
    # 解析第一个参数作为模式
    if [[ $# -gt 0 ]]; then
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            basic|ecommerce|distributed)
                mode=$1
                ;;
            --*)
                # 如果第一个参数是选项，使用默认模式
                mode="basic"
                set -- "basic" "$@"
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
