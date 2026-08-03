#!/bin/bash
# 端口配置更新脚本
# 用法: ./scripts/update_ports.sh

set -e

CONFIG_FILE="config/ports.json"

echo "=== 当前端口配置 ==="
python3 config/__init__.py

echo ""
echo "=== 如何使用 ==="
echo "1. 编辑 config/ports.json 修改端口"
echo "2. 运行 docker-compose build && docker-compose up -d 重新构建"
echo ""
echo "=== 示例 ==="
echo "修改 MCP 服务器端口为 9000:"
echo "  编辑 config/ports.json，将 mcp_server.port 改为 9000"
echo "  更新 docker-compose.yml 的端口映射: 8768:8768 -> 9000:9000"
echo "  更新 nginx/gateway.conf 的 proxy_pass"
echo ""
