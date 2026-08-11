# 任务总览

> 设计稿审批通过日期：2026-08-11
> 设计文档：[../04.ai-analyst-redesign.md](../04.ai-analyst-redesign.md)
> 本文档：任务分解索引（目录：`docs/ai-analyst-redesign-implementation/`）

---

## 任务结构

```
Phase 0 ── 数据库与基础设施（P0.1 ~ P0.3）
  ↓ 依赖
Phase 1 ── 核心引擎（P1.1 ~ P1.3）
  ↓ 依赖
Phase 2 ── 调度器（P2.1 ~ P2.3）
  ↓ 依赖
Phase 3 ── API 路由（P3.1 ~ P3.5）
  ↓ 依赖
Phase 4 ── 前端页面（P4.1 ~ P4.6）
  ↓ 依赖
Phase 5 ── 集成与部署（P5.1 ~ P5.2）
  ↓ 依赖
Phase 6 ── 验证与收尾（P6.1 ~ P6.2）
```

---

## 任务清单

| 编号 | 任务 | 前置条件 | 状态 |
|------|------|----------|:----:|
| [P0.1](P0.1-db-tables.md) | 数据库表结构 + 种子数据 | 无 | ⏳ |
| [P0.2](P0.2-dependencies.md) | 依赖安装（requirements + Dockerfile） | 无 | ⏳ |
| [P0.3](P0.3-llm-client.md) | LLM 客户端封装 | P0.2 | ⏳ |
| [P1.1](P1.1-prompt-renderer.md) | Jinja2 提示词渲染器 | 无 | ⏳ |
| [P1.2](P1.2-extraction-engine.md) | 情报结构化抽取引擎 | P0.1, P0.3, P1.1 | ⏳ |
| [P1.3](P1.3-sql-aggregator.md) | SQL 聚合引擎 | P0.1 | ⏳ |
| [P2.1](P2.1-scheduler-core.md) | 调度器核心框架 | 无 | ⏳ |
| [P2.2](P2.2-extract-flow.md) | 抽取流程实现 | P1.2, P2.1 | ⏳ |
| [P2.3](P2.3-report-flow.md) | 报告生成流程实现 | P1.3, P2.1 | ⏳ |
| [P3.1](P3.1-extract-rules-api.md) | 抽取规则 API | P0.1 | ⏳ |
| [P3.2](P3.2-report-template-api.md) | 报告模板 API | P0.1 | ⏳ |
| [P3.3](P3.3-fact-query-api.md) | 事实查询 API | P0.1 | ⏳ |
| [P3.4](P3.4-scheduler-api.md) | 调度器管理 API | P0.1, P2.1 | ⏳ |
| [P3.5](P3.5-run-api.md) | 报告执行 API | P0.1 | ⏳ |
| [P4.1](P4.1-navigation.md) | 侧栏导航 + 路由注册 | 无 | ⏳ |
| [P4.2](P4.2-intel-extract-page.md) | 抽取规则管理页 | P4.1, P3.1 | ⏳ |
| [P4.3](P4.3-reports-page.md) | 报告模板管理页 | P4.1, P3.2 | ⏳ |
| [P4.4](P4.4-report-view-page.md) | 报告查看页 | P4.1, P3.3, P3.5 | ⏳ |
| [P4.5](P4.5-analyst-page.md) | 快速执行页改造 | P4.1, P3.5 | ⏳ |
| [P4.6](P4.6-settings-update.md) | 系统设置更新 | P3.4 | ⏳ |
| [P5.1](P5.1-docker-config.md) | Docker 配置更新 | P2.1 | ⏳ |
| [P5.2](P5.2-backfill.md) | 历史情报回填抽取 | P2.2 | ⏳ |
| [P6.1](P6.1-verification.md) | 功能验收验证 | P0~P5 全部 | ⏳ |
| [P6.2](P6.2-cleanup.md) | 收尾清理 | P6.1 | ⏳ |

---

## 状态标记说明

| 标记 | 含义 |
|:----:|------|
| ⏳ | 待开始（未实施） |
| 🔧 | 进行中 |
| ✅ | 已完成（通过验证） |
| ❌ | 已放弃/取消 |
| 🔄 | 有修改，需重新验证 |

## 实施顺序说明

1. **Phase 0**：三个任务可并行开始（P0.1、P0.2 无依赖，P0.3 依赖 P0.2）
2. **Phase 1**：P1.1 可最先开始（无依赖），P1.2 和 P1.3 可并行
3. **Phase 2**：P2.1 最先开始，P2.2 和 P2.3 并行
4. **Phase 3**：P3.1 ~ P3.5 可并行
5. **Phase 4**：P4.1 最先开始，后续任务按依赖顺序
6. **Phase 5/6**：按依赖顺序

每个任务的详细规格见对应编号文件。