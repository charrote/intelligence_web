# 情报管理系统

## 技术栈
- 后端: Flask + SQLite
- 前端: 原生HTML/CSS/JS + marked.js (Markdown渲染)
- 情报采集: OpenClaw Agent（web_search + web_fetch）定时自动执行

## 状态流转
```
pending (待审阅) → approved (可行) → active (激活) → completed (已完结)
                ↘ rejected (不可行)
                ↘ discarded (已废弃) [任何状态均可废止]
```

## API接口

### POST /api/intelligence
创建情报
```json
{ "title": "xxx", "content": "markdown内容", "category": "类别" }
```

### GET /api/intelligence
列表筛选
- search: 模糊搜索标题/内容
- status: pending/approved/rejected/active/completed/discarded
- category: 分类
- date_from/date_to: 日期范围

### GET /api/intelligence/{id}
获取详情

### PUT /api/intelligence/{id}/status
更新状态
```json
{ "status": "approved|rejected|active|completed|discarded", "opinion": "意见" }
```

### POST /api/intelligence/{id}/history
添加履历
```json
{ "action": "操作名称", "detail": "详细说明", "file_location": "文件位置" }
```

### GET /api/intelligence/{id}/history
获取履历

### GET /api/categories
获取所有分类

## 运行
```bash
cd intelligence_web/api
pip install flask
python app.py
```

访问 http://localhost:8765/index.html

## 自动情报采集
系统通过 OpenClaw Agent 定时自动采集网络情报：
- **频率**: 每小时一次（cron `0 * * * *`）
- **每次最多**: 20条
- **来源**: 根据指挥板指令中的关键词，从网络搜索获取
- **去重**: 自动对比已有数据，避免重复录入