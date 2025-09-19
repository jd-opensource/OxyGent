#!/bin/bash

# OxyGent Docker 停止脚本
# 使用方法: ./docker-stop.sh [options]

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
OxyGent Docker 停止脚本

使用方法:
    $0 [OPTIONS]

选项:
    --remove-volumes    删除所有数据卷 (⚠️ 会丢失数据)
    --remove-images     删除相关镜像
    --cleanup           完全清理 (volumes + images + networks)
    --help              显示此帮助信息

示例:
    $0                              # 停止服务
    $0 --remove-volumes             # 停止并删除数据卷
    $0 --cleanup                    # 完全清理所有资源

EOF
}

# 停止服务
stop_services() {
    local remove_volumes=false
    local remove_images=false
    local cleanup=false
    local compose_file="./docker/docker-compose.yml"

    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --remove-volumes)
                remove_volumes=true
                shift
                ;;
            --remove-images)
                remove_images=true
                shift
                ;;
            --cleanup)
                cleanup=true
                remove_volumes=true
                remove_images=true
                shift
                ;;
            *)
                warn "未知参数: $1"
                shift
                ;;
        esac
    done

    log "停止 OxyGent 服务"

    # 检查使用哪个 compose 命令
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi

    # 检查并停止服务
    if [[ -f "$compose_file" ]]; then
        # 显示当前运行的服务
        if $COMPOSE_CMD -f "$compose_file" ps -q | grep -q .; then
            info "当前运行的服务:"
            $COMPOSE_CMD -f "$compose_file" ps
            
            # 停止服务
            log "停止服务..."
            $COMPOSE_CMD -f "$compose_file" down
            
            # 删除数据卷
            if [[ "$remove_volumes" == true ]]; then
                warn "删除数据卷 (数据将丢失)..."
                $COMPOSE_CMD -f "$compose_file" down -v
            fi
            
            # 删除镜像
            if [[ "$remove_images" == true ]]; then
                info "删除相关镜像..."
                $COMPOSE_CMD -f "$compose_file" down --rmi all
            fi
        else
            info "没有运行的 OxyGent 服务"
        fi
    else
        warn "Compose 文件不存在: $compose_file"
    fi

    # 完全清理
    if [[ "$cleanup" == true ]]; then
        info "执行完全清理..."
        
        # 清理未使用的网络
        log "清理 Docker 网络..."
        docker network prune -f
        
        # 清理未使用的镜像
        log "清理未使用的镜像..."
        docker image prune -f
        
        # 清理构建缓存
        log "清理构建缓存..."
        docker builder prune -f
        
        # 显示清理后的磁盘使用情况
        info "清理后的磁盘使用情况:"
        docker system df
    fi

    log "停止操作完成"
}

# 显示运行状态
show_status() {
    info "当前 OxyGent 服务状态:"
    
    local compose_file="./docker/docker-compose.yml"
    
    # 检查使用哪个 compose 命令
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi

    if [[ -f "$compose_file" ]]; then
        if $COMPOSE_CMD -f "$compose_file" ps -q | grep -q .; then
            echo
            $COMPOSE_CMD -f "$compose_file" ps
        else
            info "没有运行的 OxyGent 服务"
        fi
    else
        warn "Compose 文件不存在: $compose_file"
    fi
    
    echo
    info "Docker 资源使用情况:"
    docker system df
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
            --status)
                show_status
                exit 0
                ;;
        esac
    fi

    log "开始停止 OxyGent Docker 服务..."
    
    stop_services "$@"
    
    log "停止完成！"
}

# 执行主函数
main "$@"
