#!/bin/bash
# Kill any local MCP server, then restart Docker MCP container
set +e
pkill -9 -f "python3.*mcp_server/server.py" 2>/dev/null
kill -9 $(lsof -ti :8768) 2>/dev/null
echo "CLEANED local MCP"
cd /Users/Yoo/SVN/00.GITHUB/Intelligence_Web
docker compose restart mcp_server 2>&1
echo "DOCKER_RESTARTED"
