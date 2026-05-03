# 情报管理系统

## 技术栈
- 后端: Flask + SQLite
- 前端: 原生HTML/CSS/JS + marked.js (Markdown渲染)

## 状态流转
```
pending (待审阅) → approved (可行) → active (激活) → completed (已完结)
                ↘ rejected (不可行)
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
- status: pending/approved/rejected/active/completed
- category: 分类
- date_from/date_to: 日期范围

### GET /api/intelligence/{id}
获取详情

### PUT /api/intelligence/{id}/status
更新状态
```json
{ "status": "approved|rejected|active|completed", "opinion": "意见" }
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

访问 http://localhost:5000/web/index.html