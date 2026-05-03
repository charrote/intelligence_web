# 情报管理系统 - Agent接口文档

## 基础信息

- API地址: `http://localhost:8766`
- 数据格式: JSON

## 状态说明

| 状态 | 说明 |
|------|------|
| pending | 待审阅 |
| approved | 可行 |
| rejected | 不可行 |
| active | 激活(执行中) |
| completed | 已完结 |

## 接口列表

### 1. 创建情报

```http
POST /api/intelligence
```

```json
{
  "title": "情报标题",
  "content": "markdown格式内容",
  "category": "分类名称"
}
```

响应:
```json
{ "id": 1, "status": "pending" }
```

---

### 2. 获取情报列表

```http
GET /api/intelligence
```

筛选参数:
- `search`: 模糊搜索标题或内容
- `status`: pending/approved/rejected/active/completed
- `category`: 分类名称
- `date_from`: 开始日期 (ISO格式)
- `date_to`: 结束日期 (ISO格式)

---

### 3. 获取单条情报

```http
GET /api/intelligence/{id}
```

响应:
```json
{
  "id": 1,
  "title": "标题",
  "content": "内容",
  "category": "分类",
  "status": "pending",
  "opinion": "意见",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

---

### 4. 获取情报履历

```http
GET /api/intelligence/{id}/history
```

响应:
```json
[
  {
    "id": 1,
    "intelligence_id": 1,
    "action": "代码编写",
    "detail": "详细说明",
    "file_location": "src/main.py",
    "created_at": "2024-01-01T00:00:00"
  }
]
```

---

### 5. 获取所有分类

```http
GET /api/categories
```

---

## Agent工作流程

### 流程一：录入情报

1. 调用 `POST /api/intelligence` 创建情报
2. 状态自动为 `pending`

### 流程二：情报采集前准备

**重要**: 在开展情报搜索前，必须读取最新的指挥指令文件。

指挥指令文件路径: `data/scout_directives.md`

该文件由管理者通过"情报指挥板"设置，包含了当前情报搜集的方向和优先级。

获取指令的方式:
1. 调用 `POST /api/commands/generate` 生成指令文件（或读取已存在的 `scout_directives.md`）
2. 读取文件内容，根据其中的搜索关键词开展情报搜集
3. 关键词示例：
   - "MES 系统与 AI 集成的挑战"
   - "智能工厂的边缘计算应用"
   - "工业 4.0 实施中的问题"

### 流程三：执行可行项目

1. 等待管理员标记 `approved`
2. 调用 `GET /api/intelligence` 获取 `status=approved` 的项目
3. 获取 `opinion` 作为执行参考
4. 调用 `GET /api/intelligence/{id}/history` 查看历史履历
5. 通过 `POST /api/intelligence/{id}/history` 持续更新履历

### 履历记录格式

```json
{
  "action": "操作名称",
  "detail": "详细说明",
  "file_location": "文件或目录路径"
}
```

- action: 必填，如 "代码编写"、"环境配置"、"测试执行"
- detail: 选填，详细说明
- file_location: 选填，文件或目录路径

---

## 示例

### Python调用示例

```python
import requests

API = "http://localhost:8766"

# 创建情报
resp = requests.post(f"{API}/api/intelligence", json={
    "title": "优化数据库查询",
    "content": "## 需求\n- 优化慢查询\n\n## 方案\n添加索引",
    "category": "性能优化"
})
intel_id = resp.json()["id"]

# 获取待执行项目
resp = requests.get(f"{API}/api/intelligence", params={"status": "approved"})
for item in resp.json():
    print(f"{item['id']}: {item['title']}")

# 更新履历
requests.post(f"{API}/api/intelligence/{intel_id}/history", json={
    "action": "代码编写",
    "detail": "添加了复合索引",
    "file_location": "src/models.py"
})
```