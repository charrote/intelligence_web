#!/bin/bash
# 服务器维护脚本 — 每天 23:00 开始，每 8 小时执行一次
# 检查并修复：frp、Docker、大模型服务

LOG_FILE="/home/uantek/dev/Applications/intelligence_web/logs/maintenance.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ========== 1. 检查 FRP 服务 ==========
check_frp() {
    log "🔍 检查 FRP 服务..."
    if systemctl is-active --quiet frpc; then
        # 额外检查 frp 日志中是否有大量错误
        local errors=$(journalctl -u frpc --since "5 min ago" --no-pager 2>/dev/null | grep -c "start error: proxy.*already exists" || echo 0)
        if [ "$errors" -gt 10 ]; then
            log "⚠️ FRP 有重复代理错误，尝试重启..."
            systemctl restart frpc
            sleep 3
            if systemctl is-active --quiet frpc; then
                log "✅ FRP 服务已修复并运行正常"
            else
                log "❌ FRP 重启失败"
            fi
        else
            log "✅ FRP 服务运行正常"
        fi
    else
        log "❌ FRP 服务未运行，尝试启动..."
        systemctl start frpc
        sleep 3
        if systemctl is-active --quiet frpc; then
            log "✅ FRP 服务已启动"
        else
            log "❌ FRP 启动失败，尝试手动启动..."
            /home/uantek/dev/frp/frpc -c /home/uantek/dev/frp/frpc.toml &
            sleep 3
            if pgrep -f "frpc" > /dev/null; then
                log "✅ FRP 服务已手动启动"
            else
                log "❌ FRP 手动启动也失败"
            fi
        fi
    fi
}

# ========== 2. 检查 Docker 服务 ==========
check_docker() {
    log "🔍 检查 Docker 服务..."
    if systemctl is-active --quiet docker; then
        log "✅ Docker 服务运行正常"
    else
        log "❌ Docker 服务未运行，尝试启动..."
        systemctl start docker
        sleep 5
        if systemctl is-active --quiet docker; then
            log "✅ Docker 服务已启动"
            # 重启 intelligence_web 容器
            cd /home/uantek/dev/Applications/intelligence_web && docker-compose up -d 2>&1 | tail -3 | while read line; do log "   $line"; done
            log "✅ intelligence_web 容器已重启"
        else
            log "❌ Docker 启动失败"
        fi
    fi
}

# ========== 3. 检查大模型服务 ==========
check_llm() {
    log "🔍 检查大模型服务 (http://127.0.0.1:9234/models)..."
    local response=$(curl -s --max-time 10 http://127.0.0.1:9234/models 2>/dev/null)
    
    if [ -z "$response" ]; then
        log "❌ 大模型服务无响应，尝试重启..."
        # 检查是否有 llama-server 进程在运行
        local llama_pid=$(pgrep -f "llama-server.*9234" || echo "")
        if [ -n "$llama_pid" ]; then
            log "   发现残留进程 (PID: $llama_pid)，先终止..."
            kill -9 $llama_pid 2>/dev/null
            sleep 2
        fi
        # 启动 llama-server（根据实际配置调整）
        nohup /usr/local/bin/llama-server \
            --host 127.0.0.1 \
            --model /home/uantek/models/Qwen3.6-35B-A3B/*.gguf \
            --port 9234 \
            --n-gpu-layers 99 \
            > /home/uantek/dev/Applications/intelligence_web/logs/llama-server.log 2>&1 &
        sleep 10
        local response=$(curl -s --max-time 10 http://127.0.0.1:9234/models 2>/dev/null)
        if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print('data' in d)" 2>/dev/null; then
            log "✅ 大模型服务已启动并正常"
        else
            log "❌ 大模型服务启动失败"
        fi
    else
        # 验证返回的是有效的 JSON 且有 data 字段
        if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'data' in d" 2>/dev/null; then
            local model_count=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))")
            log "✅ 大模型服务正常，当前加载 $model_count 个模型"
        else
            log "⚠️ 大模型服务响应格式异常，尝试重启..."
            local llama_pid=$(pgrep -f "llama-server.*9234" || echo "")
            if [ -n "$llama_pid" ]; then
                kill -9 $llama_pid 2>/dev/null
                sleep 2
            fi
            nohup /usr/local/bin/llama-server \
                --host 127.0.0.1 \
                --model /home/uantek/models/Qwen3.6-35B-A3B/*.gguf \
                --port 9234 \
                --n-gpu-layers 99 \
                > /home/uantek/dev/Applications/intelligence_web/logs/llama-server.log 2>&1 &
            sleep 10
            local response=$(curl -s --max-time 10 http://127.0.0.1:9234/models 2>/dev/null)
            if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print('data' in d)" 2>/dev/null; then
                log "✅ 大模型服务已重启并正常"
            else
                log "❌ 大模型服务重启失败"
            fi
        fi
    fi
}

# ========== 主流程 ==========
log "========== 服务器维护检查开始 =========="
check_frp
check_docker
check_llm
log "========== 服务器维护检查结束 =========="
