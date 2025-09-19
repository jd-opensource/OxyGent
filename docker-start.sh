#!/bin/bash

# OxyGent Docker 启动脚本（根目录快捷方式）
# 实际脚本位于 docker/docker-start.sh

cd docker && exec ./docker-start.sh "$@"