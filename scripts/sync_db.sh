#!/bin/bash
# 同步本地数据库到远程服务器
# 使用方法: ./scripts/sync_db.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 数据库文件
SALES_DB="$PROJECT_DIR/intelligence_sales/data/intelligence_sales"
RESEARCH_DB="$PROJECT_DIR/intelligence_web/data/intelligence.db"

# 远程服务器信息（根据实际情况修改）
REMOTE_HOST="${1:-your-server-ip}"
REMOTE_USER="${2:-your-username}"
REMOTE_PATH="${3:-/path/to/Intelligence_Web}"

echo "=========================================="
echo "数据库同步脚本"
echo "=========================================="
echo ""

# 检查本地数据库文件
if [ ! -f "$SALES_DB" ]; then
    echo "❌ 销售情报域数据库不存在: $SALES_DB"
    exit 1
fi

if [ ! -f "$RESEARCH_DB" ]; then
    echo "❌ 制造情报域数据库不存在: $RESEARCH_DB"
    exit 1
fi

echo "✅ 本地数据库文件:"
echo "   销售情报: $SALES_DB ($(du -h "$SALES_DB" | cut -f1))"
echo "   制造情报: $RESEARCH_DB ($(du -h "$RESEARCH_DB" | cut -f1))"
echo ""

# 显示数据量
echo "📊 本地数据量:"
echo "   销售情报域: $(sqlite3 "$SALES_DB" "SELECT COUNT(*) FROM intelligence;" 2>/dev/null || echo "0") 条情报"
echo "   销售情报域: $(sqlite3 "$SALES_DB" "SELECT COUNT(*) FROM datasources;" 2>/dev/null || echo "0") 个数据源"
echo "   销售情报域: $(sqlite3 "$SALES_DB" "SELECT COUNT(*) FROM projects;" 2>/dev/null || echo "0") 个项目"
echo ""

# 同步到远程服务器
echo "🔄 开始同步到远程服务器..."
echo "   目标：$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"
echo ""

# 停止远程容器（可选，避免写入冲突）
echo "1/4 停止远程容器..."
ssh "$REMOTE_USER@$REMOTE_HOST" "cd $REMOTE_PATH && docker compose down research sales 2>/dev/null || true"

# 复制数据库文件
echo "2/4 复制数据库文件..."
scp "$SALES_DB" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/intelligence_sales/data/intelligence_sales"
scp "$RESEARCH_DB" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/intelligence_web/data/intelligence.db"

# 设置权限
echo "3/4 设置文件权限..."
ssh "$REMOTE_USER@$REMOTE_HOST" "cd $REMOTE_PATH && chmod 664 intelligence_sales/data/intelligence_sales intelligence_web/data/intelligence.db"

# 启动容器
echo "4/4 启动远程容器..."
ssh "$REMOTE_USER@$REMOTE_HOST" "cd $REMOTE_PATH && docker compose up -d research sales"

echo ""
echo "=========================================="
echo "✅ 同步完成！"
echo "=========================================="
echo ""
echo "请验证远程服务："
echo "  curl http://$REMOTE_HOST:8767/api/health"
echo "  curl http://$REMOTE_HOST:8766/api/health"
echo ""
echo "查看数据源："
echo "  curl -u admin:admin123 http://$REMOTE_HOST:8767/api/datasources"