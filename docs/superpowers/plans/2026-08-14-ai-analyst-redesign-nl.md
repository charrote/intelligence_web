# AI 分析师重构 - 自然语言自动配置

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 AI 分析师从"复杂配置"重构为"自然语言输入 + AI 自动配置 + 报告管理"，用户零配置即可使用

**架构：** 
- 新增 `ai_analysis_config` 表存储 AI 自动生成的分析配置
- 新增 `ai_analysis_run` 表存储报告执行记录
- 用户输入自然语言 → AI 识别意图 → 自动生成配置 → 执行分析 → 生成报告
- 支持预设快捷入口 + 报告管理（修改/删除/启停）

**技术栈：** Flask + Python 3.11 + SQLite + Vanilla HTML/CSS/JS

---

## 全局约束

- 不修改 `intelligence` 表结构（保持不变）
- 所有 AI 配置持久化到 `ai_analysis_config` 表
- 所有报告执行记录到 `ai_analysis_run` 表
- 前端使用现有 CSS 变量（`css/variables.css`）
- 禁止 Emoji，图标用 ant-design icons SVG
- 模态窗 centered + maxHeight
- Tab 激活态 `#3B82F6`，未激活态 `rgba(255,255,255,0.5)`
- 文案去 AI 化，用工程师视角

---

## 任务 1：数据库层 - 新增 ai_analysis_config 表

**文件：**
- 创建：无
- 修改：`core/db.py`

### 步骤 1：新增 ai_analysis_config 表定义

```sql
CREATE TABLE IF NOT EXISTS ai_analysis_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,                    -- 域标识：research / sales
    name TEXT NOT NULL,                      -- 配置名称（用户可见）
    description TEXT DEFAULT '',             -- 配置描述
    
    -- AI 自动生成的分析配置
    intent TEXT DEFAULT '',                  -- 用户原始意图（自然语言）
    entity_type TEXT DEFAULT '',             -- 实体类型：厂商/市场/技术/商机/投资/区域
    time_range TEXT DEFAULT '30',            -- 时间范围：7/14/30/60/90 天
    group_by TEXT DEFAULT '',                -- 分组维度：entity_name / time_period / context
    metrics_config TEXT DEFAULT '[]',        -- 聚合指标配置（JSON）
    filters_config TEXT DEFAULT '[]',        -- 过滤条件配置（JSON）
    chart_config TEXT DEFAULT '[]',          -- 图表配置（JSON）
    llm_prompt TEXT DEFAULT '',              -- LLM 分析 Prompt 模板
    
    -- 状态管理
    enabled INTEGER DEFAULT 1,               -- 是否启用：1=启用，0=停用
    status TEXT DEFAULT 'draft',             -- 状态：draft（草稿）/ active（启用）/ archived（归档）
    
    -- 元数据
    source TEXT DEFAULT 'user_input',        -- 来源：user_input / preset / auto
    sort_order INTEGER DEFAULT 0,            -- 排序
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 步骤 2：在 init_db 中注册新表

在 `core/db.py` 的 `init_db` 函数中，在现有表定义之后添加上述 CREATE TABLE 语句。

### 步骤 3：添加表初始化验证

在 `init_db` 函数的验证逻辑中加入 `ai_analysis_config` 表的验证。

---

## 任务 2：数据库层 - 新增 ai_analysis_run 表

**文件：**
- 修改：`core/db.py`

### 步骤 1：新增 ai_analysis_run 表定义

```sql
CREATE TABLE IF NOT EXISTS ai_analysis_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER DEFAULT NULL,          -- 关联的分析配置（NULL=临时分析）
    domain TEXT NOT NULL,                    -- 域标识
    title TEXT NOT NULL,                     -- 报告标题
    
    -- 执行状态
    status TEXT DEFAULT 'pending',           -- pending / running / completed / failed
    progress INTEGER DEFAULT 0,              -- 进度：0-100
    error_msg TEXT DEFAULT '',               -- 错误信息（失败时）
    
    -- 分析结果
    result_markdown TEXT DEFAULT '',         -- Markdown 格式的分析报告
    result_charts TEXT DEFAULT '[]',         -- 图表数据（JSON 数组）
    result_summary TEXT DEFAULT '',          -- 分析摘要
    result_data TEXT DEFAULT '[]',           -- 原始数据（JSON 数组）
    
    -- 执行元数据
    lookback_days INTEGER DEFAULT 30,        -- 数据范围（天）
    execution_time_ms INTEGER DEFAULT 0,     -- 执行耗时（毫秒）
    start_time TEXT NOT NULL,                -- 开始时间
    end_time TEXT DEFAULT NULL,              -- 结束时间
    
    -- 元数据
    created_by TEXT DEFAULT '',              -- 创建者（用户）
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 步骤 2：在 init_db 中注册新表

在 `core/db.py` 的 `init_db` 函数中，在 `ai_analysis_config` 表之后添加上述 CREATE TABLE 语句。

### 步骤 3：添加表初始化验证

在 `init_db` 函数的验证逻辑中加入 `ai_analysis_run` 表的验证。

---

## 任务 3：数据库层 - 配置管理 CRUD

**文件：**
- 修改：`core/db.py`

### 步骤 1：添加配置查询函数

```python
def get_ai_analysis_configs(project_root, spec, domain=None, enabled=None):
    """查询分析配置列表"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    query = "SELECT * FROM ai_analysis_config WHERE 1=1"
    params = []
    
    if domain:
        query += " AND domain = ?"
        params.append(domain)
    
    if enabled is not None:
        query += " AND enabled = ?"
        params.append(1 if enabled else 0)
    
    query += " ORDER BY sort_order ASC, updated_at DESC"
    
    c.execute(query, params)
    configs = [dict(row) for row in c.fetchall()]
    conn.close()
    return configs

def get_ai_analysis_config_by_id(project_root, spec, config_id):
    """根据 ID 查询配置"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    c.execute("SELECT * FROM ai_analysis_config WHERE id = ?", (config_id,))
    config = c.fetchone()
    conn.close()
    return dict(config) if config else None

def save_ai_analysis_config(project_root, spec, config_data):
    """保存分析配置（新增或更新）"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    if config_data.get("id"):
        # 更新
        c.execute("""
            UPDATE ai_analysis_config SET
                domain = ?, name = ?, description = ?, intent = ?,
                entity_type = ?, time_range = ?, group_by = ?,
                metrics_config = ?, filters_config = ?, chart_config = ?,
                llm_prompt = ?, enabled = ?, status = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            config_data["domain"], config_data["name"], config_data.get("description", ""),
            config_data.get("intent", ""), config_data.get("entity_type", ""),
            config_data.get("time_range", "30"), config_data.get("group_by", ""),
            json.dumps(config_data.get("metrics_config", [])),
            json.dumps(config_data.get("filters_config", [])),
            json.dumps(config_data.get("chart_config", [])),
            config_data.get("llm_prompt", ""), config_data.get("enabled", 1),
            config_data.get("status", "active"),
            datetime.utcnow().isoformat(), config_data["id"]
        ))
    else:
        # 新增
        c.execute("""
            INSERT INTO ai_analysis_config (
                domain, name, description, intent, entity_type, time_range,
                group_by, metrics_config, filters_config, chart_config,
                llm_prompt, enabled, status, source, sort_order,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config_data["domain"], config_data["name"], config_data.get("description", ""),
            config_data.get("intent", ""), config_data.get("entity_type", ""),
            config_data.get("time_range", "30"), config_data.get("group_by", ""),
            json.dumps(config_data.get("metrics_config", [])),
            json.dumps(config_data.get("filters_config", [])),
            json.dumps(config_data.get("chart_config", [])),
            config_data.get("llm_prompt", ""), config_data.get("enabled", 1),
            config_data.get("status", "draft"), config_data.get("source", "user_input"),
            config_data.get("sort_order", 0),
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
        ))
    
    conn.commit()
    conn.close()
    return True

def delete_ai_analysis_config(project_root, spec, config_id):
    """删除分析配置"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    c.execute("DELETE FROM ai_analysis_config WHERE id = ?", (config_id,))
    conn.commit()
    conn.close()
    return True
```

---

## 任务 4：数据库层 - 报告执行 CRUD

**文件：**
- 修改：`core/db.py`

### 步骤 1：添加报告执行记录管理函数

```python
def get_ai_analysis_runs(project_root, spec, config_id=None, limit=20, offset=0):
    """查询报告执行记录"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    query = "SELECT id, config_id, domain, title, status, progress, error_msg, result_summary, start_time, end_time, execution_time_ms, created_at FROM ai_analysis_run WHERE 1=1"
    params = []
    
    if config_id:
        query += " AND config_id = ?"
        params.append(config_id)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    c.execute(query, params)
    runs = [dict(row) for row in c.fetchall()]
    conn.close()
    return runs

def get_ai_analysis_run_by_id(project_root, spec, run_id):
    """根据 ID 查询报告执行记录"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    c.execute("SELECT * FROM ai_analysis_run WHERE id = ?", (run_id,))
    run = c.fetchone()
    conn.close()
    return dict(run) if run else None

def save_ai_analysis_run(project_root, spec, run_data):
    """保存报告执行记录"""
    db_path = get_db_path(project_root, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    if run_data.get("id"):
        c.execute("""
            UPDATE ai_analysis_run SET
                status = ?, progress = ?, error_msg = ?,
                result_markdown = ?, result_charts = ?, result_summary = ?,
                result_data = ?, execution_time_ms = ?, end_time = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            run_data["status"], run_data.get("progress", 0),
            run_data.get("error_msg", ""),
            run_data.get("result_markdown", ""),
            json.dumps(run_data.get("result_charts", [])),
            run_data.get("result_summary", ""),
            json.dumps(run_data.get("result_data", [])),
            run_data.get("execution_time_ms", 0),
            datetime.utcnow().isoformat() if run_data["status"] in ["completed", "failed"] else None,
            datetime.utcnow().isoformat(), run_data["id"]
        ))
    else:
        c.execute("""
            INSERT INTO ai_analysis_run (
                config_id, domain, title, status, progress, error_msg,
                result_markdown, result_charts, result_summary, result_data,
                lookback_days, execution_time_ms, start_time, end_time,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data.get("config_id"), run_data["domain"], run_data["title"],
            run_data["status"], run_data.get("progress", 0),
            run_data.get("error_msg", ""),
            run_data.get("result_markdown", ""),
            json.dumps(run_data.get("result_charts", [])),
            run_data.get("result_summary", ""),
            json.dumps(run_data.get("result_data", [])),
            run_data.get("lookback_days", 30),
            run_data.get("execution_time_ms", 0),
            run_data["start_time"], run_data.get("end_time"),
            run_data.get("created_by", ""),
            datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
        ))
    
    conn.commit()
    conn.close()
    return True
```

---

## 任务 5：后端 API - 分析配置 CRUD

**文件：**
- 修改：`core/app.py`

### 步骤 1：添加配置路由

```python
@app.route('/api/ai/analysis/configs', methods=['GET'])
@require_auth
def api_ai_analysis_configs():
    """获取分析配置列表"""
    spec = get_current_spec()
    domain = request.args.get('domain')
    enabled = request.args.get('enabled')
    
    if enabled is not None:
        enabled = int(enabled)
    
    configs = get_ai_analysis_configs(app.instance_path, spec, domain=domain, enabled=enabled)
    return jsonify(configs)

@app.route('/api/ai/analysis/configs/<int:config_id>', methods=['GET'])
@require_auth
def api_ai_analysis_config_detail(config_id):
    """获取分析配置详情"""
    spec = get_current_spec()
    config = get_ai_analysis_config_by_id(app.instance_path, spec, config_id)
    if not config:
        return jsonify({"error": "Config not found"}), 404
    return jsonify(config)

@app.route('/api/ai/analysis/configs', methods=['POST'])
@require_auth
def api_ai_analysis_config_create():
    """创建分析配置"""
    spec = get_current_spec()
    data = request.json
    
    if not all(k in data for k in ['domain', 'name', 'intent']):
        return jsonify({"error": "Missing required fields: domain, name, intent"}), 400
    
    save_ai_analysis_config(app.instance_path, spec, data)
    return jsonify({"success": True, "id": get_last_insert_id()})

@app.route('/api/ai/analysis/configs/<int:config_id>', methods=['PUT'])
@require_auth
def api_ai_analysis_config_update(config_id):
    """更新分析配置"""
    spec = get_current_spec()
    data = request.json
    data['id'] = config_id
    
    existing = get_ai_analysis_config_by_id(app.instance_path, spec, config_id)
    if not existing:
        return jsonify({"error": "Config not found"}), 404
    
    save_ai_analysis_config(app.instance_path, spec, data)
    return jsonify({"success": True})

@app.route('/api/ai/analysis/configs/<int:config_id>', methods=['DELETE'])
@require_auth
def api_ai_analysis_config_delete(config_id):
    """删除分析配置"""
    spec = get_current_spec()
    delete_ai_analysis_config(app.instance_path, spec, config_id)
    return jsonify({"success": True})
```

---

## 任务 6：后端 API - 自然语言分析入口

**文件：**
- 修改：`core/app.py`

### 步骤 1：添加自然语言分析路由

```python
@app.route('/api/ai/analysis/run', methods=['POST'])
@require_auth
def api_ai_analysis_run():
    """自然语言分析入口"""
    spec = get_current_spec()
    data = request.json
    
    if not data or 'intent' not in data:
        return jsonify({"error": "Missing 'intent' field"}), 400
    
    intent = data['intent']
    lookback_days = data.get('lookback_days', 30)
    
    # 调用 AI 分析
    result = run_ai_analysis(spec, intent, lookback_days)
    return jsonify(result)

def run_ai_analysis(spec, intent, lookback_days):
    """执行 AI 分析"""
    start_time = datetime.utcnow()
    
    # 1. 查询结构化数据
    db_path = get_db_path(app.instance_path, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    
    # 查询 intelligence 表
    query = """
        SELECT id, title, content, company, category, status, 
               contact_name, deal_value, industry, source_url, created_at
        FROM intelligence
        WHERE created_at >= ?
        ORDER BY created_at DESC
    """
    cutoff_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    c.execute(query, (cutoff_date,))
    intelligence_list = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    # 2. 调用 LLM 分析
    llm_result = call_llm_analysis(intent, intelligence_list, spec)
    
    # 3. 保存执行记录
    run_id = save_ai_analysis_run(app.instance_path, spec, {
        "domain": spec["slug"],
        "title": intent[:50],
        "status": "completed",
        "result_markdown": llm_result.get("markdown", ""),
        "result_charts": llm_result.get("charts", []),
        "result_summary": llm_result.get("summary", ""),
        "result_data": llm_result.get("data", []),
        "lookback_days": lookback_days,
        "start_time": start_time.isoformat(),
        "execution_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
    })
    
    return {
        "success": True,
        "run_id": run_id,
        "result_markdown": llm_result.get("markdown", ""),
        "result_charts": llm_result.get("charts", []),
        "result_summary": llm_result.get("summary", "")
    }
```

---

## 任务 7：前端 - 重写 analyst.html

**文件：**
- 修改：`portal/analyst.html`

### 步骤 1：页面结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 分析师</title>
    <link rel="stylesheet" href="css/variables.css">
    <link rel="stylesheet" href="css/reset.css">
    <link rel="stylesheet" href="css/header.css">
    <link rel="stylesheet" href="css/sidebar.css">
    <link rel="stylesheet" href="css/layout.css">
    <link rel="stylesheet" href="css/components.css">
    <link rel="stylesheet" href="css/responsive.css">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <script src="js/dom.js"></script>
    <script src="js/auth.js"></script>
    <script src="js/init.js"></script>
    <script src="js/tabs.js"></script>
    <style>
        /* 复用现有样式 */
    </style>
</head>
<body>
    <main class="main">
        <!-- 分析输入区 -->
        <div class="card" id="analysisInputCard">
            <div class="card-head">
                <h2>AI 分析</h2>
            </div>
            <div class="card-body">
                <!-- 自然语言输入 -->
                <div class="form-group">
                    <label class="form-label">描述你想分析的内容</label>
                    <textarea class="form-textarea" id="intentInput" rows="3" 
                              placeholder="例：最近各厂商的市场份额变化"></textarea>
                </div>
                
                <!-- 时间范围 -->
                <div class="form-group">
                    <label class="form-label">时间范围</label>
                    <div class="radio-group" id="timeRangeGroup">
                        <label><input type="radio" name="lookback" value="7" checked> 近 7 天</label>
                        <label><input type="radio" name="lookback" value="14"> 近 14 天</label>
                        <label><input type="radio" name="lookback" value="30"> 近 30 天</label>
                        <label><input type="radio" name="lookback" value="60"> 近 60 天</label>
                        <label><input type="radio" name="lookback" value="90"> 近 90 天</label>
                    </div>
                </div>
                
                <!-- 执行按钮 -->
                <div class="exec-wrap">
                    <button class="btn-exec" id="execBtn" onclick="startAnalysis()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                        </svg>
                        开始分析
                    </button>
                </div>
            </div>
        </div>
        
        <!-- 预设快捷入口 -->
        <div class="card" id="presetCard">
            <div class="card-head">
                <h2>快速分析</h2>
            </div>
            <div class="card-body">
                <div class="preset-grid" id="presetGrid">
                    <button class="preset-btn" onclick="quickAnalysis('市场份额概览')">市场份额概览</button>
                    <button class="preset-btn" onclick="quickAnalysis('竞争对手追踪')">竞争对手追踪</button>
                    <button class="preset-btn" onclick="quickAnalysis('技术趋势分析')">技术趋势分析</button>
                    <button class="preset-btn" onclick="quickAnalysis('商机分析')">商机分析</button>
                    <button class="preset-btn" onclick="quickAnalysis('投资动态')">投资动态</button>
                    <button class="preset-btn" onclick="quickAnalysis('区域分布')">区域分布</button>
                </div>
            </div>
        </div>
        
        <!-- 进度区 -->
        <div class="card" id="progressCard" style="display:none">
            <div class="card-head">
                <h2>分析进度</h2>
            </div>
            <div class="card-body">
                <!-- 复用现有进度样式 -->
            </div>
        </div>
        
        <!-- 结果区 -->
        <div class="card" id="resultCard" style="display:none">
            <div class="card-head">
                <h2>分析结果</h2>
            </div>
            <div class="card-body">
                <div class="result-header" id="resultHeader"></div>
                <div class="markdown-content" id="resultMarkdown"></div>
                <div id="resultCharts"></div>
                <div class="summary-box" id="resultSummary" style="display:none">
                    <div class="summary-label">摘要</div>
                    <div id="resultSummaryText"></div>
                </div>
            </div>
        </div>
        
        <!-- 报告管理区 -->
        <div class="card" id="reportManageCard">
            <div class="card-head">
                <h2>分析报告</h2>
                <div class="card-head-actions">
                    <button class="btn-icon" onclick="loadReports()">刷新</button>
                </div>
            </div>
            <div class="card-body">
                <div id="reportList"></div>
            </div>
        </div>
    </main>
    
    <script>
        // 核心逻辑
    </script>
</body>
</html>
```

### 步骤 2：核心 JavaScript

```javascript
// 状态
var currentAnalysis = null;
var reportList = [];

// 自然语言分析
async function startAnalysis() {
    const intent = document.getElementById('intentInput').value.trim();
    const lookback = document.querySelector('input[name="lookback"]:checked').value;
    
    if (!intent) {
        alert('请输入分析需求');
        return;
    }
    
    // 显示进度
    document.getElementById('progressCard').style.display = 'block';
    document.getElementById('resultCard').style.display = 'none';
    document.getElementById('execBtn').disabled = true;
    
    try {
        const res = await fetch('/api/ai/analysis/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': getAuthHeader() },
            body: JSON.stringify({ intent, lookback_days: parseInt(lookback) })
        });
        
        const data = await res.json();
        
        if (data.success) {
            showResult(data);
        } else {
            alert(data.error || '分析失败');
        }
    } catch (e) {
        alert('网络错误：' + e.message);
    } finally {
        document.getElementById('progressCard').style.display = 'none';
        document.getElementById('execBtn').disabled = false;
    }
}

// 预设快捷分析
async function quickAnalysis(presetName) {
    document.getElementById('intentInput').value = presetName;
    startAnalysis();
}

// 显示结果
function showResult(data) {
    document.getElementById('resultCard').style.display = 'block';
    document.getElementById('resultMarkdown').innerHTML = marked.parse(data.result_markdown);
    
    if (data.result_charts && data.result_charts.length > 0) {
        renderCharts(data.result_charts, 'result-charts');
    }
    
    if (data.result_summary) {
        document.getElementById('resultSummary').style.display = 'block';
        document.getElementById('resultSummaryText').textContent = data.result_summary;
    }
    
    // 刷新报告列表
    loadReports();
}

// 加载报告列表
async function loadReports() {
    const res = await fetch('/api/ai/analysis/runs?limit=50', {
        headers: { 'Authorization': getAuthHeader() }
    });
    
    const data = await res.json();
    reportList = data;
    renderReportList(data);
}

// 渲染报告列表
function renderReportList(reports) {
    const container = document.getElementById('reportList');
    
    if (reports.length === 0) {
        container.innerHTML = '<p style="color:var(--gray-400);text-align:center;padding:20px">暂无分析报告</p>';
        return;
    }
    
    container.innerHTML = reports.map(report => `
        <div class="report-item" onclick="viewReport(${report.id})">
            <div class="report-title">${report.title}</div>
            <div class="report-meta">
                <span class="status-badge ${report.status}">${report.status}</span>
                <span>${report.start_time}</span>
                <span>${report.execution_time_ms}ms</span>
            </div>
        </div>
    `).join('');
}

// 查看报告详情
async function viewReport(runId) {
    const res = await fetch(`/api/ai/analysis/runs/${runId}`, {
        headers: { 'Authorization': getAuthHeader() }
    });
    
    const data = await res.json();
    
    document.getElementById('resultCard').style.display = 'block';
    document.getElementById('resultMarkdown').innerHTML = marked.parse(data.result_markdown);
    
    if (data.result_charts && data.result_charts.length > 0) {
        renderCharts(data.result_charts, 'result-charts');
    }
    
    if (data.result_summary) {
        document.getElementById('resultSummary').style.display = 'block';
        document.getElementById('resultSummaryText').textContent = data.result_summary;
    }
    
    document.getElementById('resultCard').scrollIntoView({ behavior: 'smooth' });
}

// 图表渲染（复用现有逻辑）
function renderCharts(charts, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    
    charts.forEach((chart, idx) => {
        const chartDiv = document.createElement('div');
        chartDiv.className = 'chart-container';
        chartDiv.innerHTML = `
            <div class="chart-header">
                <span>${chart.title}</span>
                <span class="chart-type ${chart.type}">${chart.type}</span>
            </div>
            <div class="chart-body" id="chart-${idx}"></div>
        `;
        container.appendChild(chartDiv);
        
        const instance = echarts.init(document.getElementById(`chart-${idx}`));
        instance.setOption(chart.option);
        chartInstances.push(instance);
    });
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadReports();
});
```

---

## 任务 8：前端 - 报告管理 CRUD

**文件：**
- 修改：`portal/analyst.html`

### 步骤 1：添加报告管理按钮

在报告列表的每个报告项中添加操作按钮：

```html
<div class="report-item">
    <div class="report-title">${report.title}</div>
    <div class="report-meta">
        <span class="status-badge ${report.status}">${report.status}</span>
        <span>${report.start_time}</span>
        <span>${report.execution_time_ms}ms</span>
    </div>
    <div class="report-actions">
        <button class="btn-icon" onclick="viewReport(${report.id})" title="查看">查看</button>
        <button class="btn-icon" onclick="editReport(${report.id})" title="修改">修改</button>
        <button class="btn-icon" onclick="deleteReport(${report.id})" title="删除">删除</button>
    </div>
</div>
```

### 步骤 2：添加删除功能

```javascript
async function deleteReport(runId) {
    if (!confirm('确定删除此报告？')) return;
    
    const res = await fetch(`/api/ai/analysis/runs/${runId}`, {
        method: 'DELETE',
        headers: { 'Authorization': getAuthHeader() }
    });
    
    if (res.ok) {
        loadReports();
    } else {
        alert('删除失败');
    }
}
```

### 步骤 3：添加修改功能（编辑弹窗）

```javascript
function editReport(runId) {
    // 显示编辑弹窗
    // 包含：标题、分析意图、时间范围、启用/停用
    // 保存后重新执行分析
}
```

---

## 任务 9：后端 API - 报告管理 CRUD

**文件：**
- 修改：`core/app.py`

### 步骤 1：添加报告路由

```python
@app.route('/api/ai/analysis/runs', methods=['GET'])
@require_auth
def api_ai_analysis_runs():
    """获取报告列表"""
    spec = get_current_spec()
    config_id = request.args.get('config_id')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    runs = get_ai_analysis_runs(app.instance_path, spec, config_id=config_id, limit=limit, offset=offset)
    return jsonify(runs)

@app.route('/api/ai/analysis/runs/<int:run_id>', methods=['GET'])
@require_auth
def api_ai_analysis_run_detail(run_id):
    """获取报告详情"""
    spec = get_current_spec()
    run = get_ai_analysis_run_by_id(app.instance_path, spec, run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run)

@app.route('/api/ai/analysis/runs/<int:run_id>', methods=['DELETE'])
@require_auth
def api_ai_analysis_run_delete(run_id):
    """删除报告"""
    spec = get_current_spec()
    # 删除执行记录
    db_path = get_db_path(app.instance_path, spec.get("db_filename") or spec["slug"])
    conn = get_db_connection(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM ai_analysis_run WHERE id = ?", (run_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/ai/analysis/runs/<int:run_id>/re-run', methods=['POST'])
@require_auth
def api_ai_analysis_run_re_run(run_id):
    """重新执行报告"""
    spec = get_current_spec()
    run = get_ai_analysis_run_by_id(app.instance_path, spec, run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404
    
    # 重新执行分析
    result = run_ai_analysis(spec, run["title"], run.get("lookback_days", 30))
    return jsonify(result)
```

---

## 任务 10：测试验证

**文件：**
- 无

### 步骤 1：启动服务

```bash
cd /Users/Yoo/SVN/00.GITHUB/intelligence_web_lab
docker compose up -d
```

### 步骤 2：测试分析功能

1. 登录系统
2. 访问 AI 分析师页面
3. 输入自然语言分析需求
4. 验证结果展示
5. 测试预设快捷入口
6. 测试报告管理（查看、修改、删除）

### 步骤 3：验证数据库

```bash
sqlite3 intelligence_web/data/research.db ".tables"
# 应显示 ai_analysis_config, ai_analysis_run 等表
```

---

## 验收标准

| # | 验收项 | 验证方式 |
|---|--------|----------|
| 1 | 数据库表创建成功 | 检查 `ai_analysis_config` 和 `ai_analysis_run` 表存在 |
| 2 | 自然语言分析入口可用 | 输入需求 → 显示进度 → 显示结果 |
| 3 | 预设快捷入口可用 | 点击预设按钮 → 自动执行分析 |
| 4 | 报告列表显示正确 | 历史报告按时间倒序显示 |
| 5 | 报告详情可查看 | 点击报告 → 显示完整分析结果 |
| 6 | 报告可删除 | 删除后列表刷新，数据库无记录 |
| 7 | 报告可重新执行 | 点击"重新执行" → 生成新报告 |
| 8 | 前端无 JS 报错 | DevTools 控制台无错误 |

---

## 注意事项

1. **AI 配置持久化**：用户每次分析都保存到 `ai_analysis_config` 表
2. **报告执行记录**：每次执行都保存到 `ai_analysis_run` 表
3. **LLM 调用**：使用现有的 LLM 客户端（`core/notify.py` 中的 `call_llm`）
4. **错误处理**：分析失败时记录错误信息，不阻断后续操作
5. **性能优化**：大结果集使用分页查询

---

## 计划完成时间估算

- 任务 1-4（数据库层）：30 分钟
- 任务 5-6（后端 API）：45 分钟
- 任务 7-8（前端重写）：60 分钟
- 任务 9-10（测试验证）：30 分钟
- **总计：约 2.75 小时**

---

**计划已完成并保存到 `docs/superpowers/plans/2026-08-14-ai-analyst-redesign-nl.md`。两种执行方式：**

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点供审查

**选哪种方式？**
