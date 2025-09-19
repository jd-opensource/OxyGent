#!/bin/bash

# Docker Compose 停止脚本 for OxyGent
# 使用方法: ./docker-stop.sh [basic|ecommerce|distributed] [options]

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
OxyGent Docker Compose 停止脚本

使用方法:
    $0 [MODE] [OPTIONS]

模式:
    basic           停止基础单服务部署 (默认)
    ecommerce       停止电商分布式示例部署
    distributed     停止分布式计算示例部署
    all             停止所有模式的部署

选项:
    --remove-volumes    删除所有数据卷 (⚠️ 会丢失数据)
    --remove-images     删除相关镜像
    --cleanup           完全清理 (volumes + images + networks)
    --help              显示此帮助信息

示例:
    $0                              # 停止基础部署
    $0 ecommerce                    # 停止电商部署
    $0 all --cleanup                # 停止所有服务并完全清理
    $0 basic --remove-volumes       # 停止基础部署并删除数据卷

EOF
}

# 停止服务
stop_services() {
    local mode=$1
    local remove_volumes=false
    local remove_images=false
    local cleanup=false
    local compose_files=()

    # 解析参数
    shift
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

    # 选择 compose 文件
    case $mode in
        ecommerce)
            compose_files=("./docker/docker-compose.ecommerce.yml")
            log "停止电商分布式部署"
            ;;
        distributed)
            compose_files=("./docker/docker-compose.distributed.yml")
            log "停止分布式计算部署"
            ;;
        all)
            compose_files=("./docker/docker-compose.yml" "./docker/docker-compose.ecommerce.yml" "./docker/docker-compose.distributed.yml")
            log "停止所有部署"
            ;;
        basic|*)
            compose_files=("./docker/docker-compose.yml")
            log "停止基础部署"
            ;;
    esac

    # 停止每个 compose 文件的服务
    for compose_file in "${compose_files[@]}"; do
        if [[ -f "$compose_file" ]]; then
            info "处理: $compose_file"
            
            # 显示当前运行的服务
            if docker-compose -f "$compose_file" ps -q | grep -q .; then
                info "当前运行的服务:"
                docker-compose -f "$compose_file" ps
                
                # 停止服务
                log "停止服务..."
                docker-compose -f "$compose_file" down
                
                # 删除数据卷
                if [[ "$remove_volumes" == true ]]; then
                    warn "删除数据卷 (数据将丢失)..."
                    docker-compose -f "$compose_file" down -v
                fi
                
                # 删除镜像
                if [[ "$remove_images" == true ]]; then
                    info "删除相关镜像..."
                    docker-compose -f "$compose_file" down --rmi all
                fi
            else
                info "没有运行的服务: $compose_file"
            fi
        else
            warn "Compose 文件不存在: $compose_file"
        fi
    done

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
    info "当前 Docker 服务状态:"
    
    local compose_files=("./docker/docker-compose.yml" "./docker/docker-compose.ecommerce.yml" "./docker/docker-compose.distributed.yml")
    local has_running=false
    
    for compose_file in "${compose_files[@]}"; do
        if [[ -f "$compose_file" ]]; then
            if docker-compose -f "$compose_file" ps -q | grep -q .; then
                echo
                info "$compose_file 运行状态:"
                docker-compose -f "$compose_file" ps
                has_running=true
            fi
        fi
    done
    
    if [[ "$has_running" == false ]]; then
        info "没有运行的 OxyGent 服务"
    fi
    
    echo
    info "Docker 资源使用情况:"
    docker system df
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
            --status)
                show_status
                exit 0
                ;;
            basic|ecommerce|distributed|all)
                mode=$1
                ;;
            --*)
                # 如果第一个参数是选项，使用默认模式
                mode="basic"
                set -- "basic" "$@"
                ;;
        esac
    fi

    log "开始停止 OxyGent Docker 服务..."
    
    stop_services "$@"
    
    log "停止完成！"
}

# 执行主函数
main "$@"
