#!/bin/bash
# Kill any local MCP server on port 8768 (non-Docker)
pkill -9 -f "python3.*mcp_server/server.py" 2>/dev/null
# Kill any process on port 8768
kill -9 $(lsof -ti :8768) 2>/dev/null
echo "CLEANED"
