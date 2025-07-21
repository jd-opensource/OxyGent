#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

cleanup() {
    log "Cleaning up processes..."
    jobs -p | xargs -r kill 2>/dev/null || true
    wait 2>/dev/null || true
    log "Cleanup complete"
}

trap cleanup EXIT INT TERM

start_service() {
    local cmd=$1
    local name=$2
    local wait_time=${3:-5}
    
    log "Starting $name..."
    $cmd &
    local pid=$!
    
    sleep $wait_time
    
    # Check if the process is still running
    if kill -0 $pid 2>/dev/null; then
        log "$name started successfully (PID: $pid)"
        return 0
    else
        error "$name failed to start"
        return 1
    fi
}

main() {
    log "Starting distributed services..."
    
    start_service "python -m examples.distributed.app_time_agent" "TimeAgent" 5
    start_service "python -m examples.distributed.app_math_agent" "MathAgent" 5
    start_service "python -m examples.distributed.app_master_agent" "MasterAgent" 5
    
    log "All services have been started"
    log "Press Ctrl+C to stop all services"
    
    wait
}

main "$@"
