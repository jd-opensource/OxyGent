#!/bin/bash

# OxyGent Docker 停止脚本（根目录快捷方式）
# 实际脚本位于 docker/docker-stop.sh

cd docker && exec ./docker-stop.sh "$@"