# 重构前后目录

基线：main / origin/main `dc7dc3337da9627a5a3c10f3a76144c272bfa37f`。开始时工作区干净、没有冲突，fetch 后双方相差 0 个提交。当前分支 `refactor/package-layout`，未提交、未推送。

## 重构前

```text
根目录：43 个平铺 Python 业务模块 + README/架构/部署/测试/发布 Markdown
scripts/  tests/  evaluation/  deploy/  documents/  verification/
```

## 重构后

```text
app/
  main.py
  api/          routes.py
  core/         config, deployment_config, context_manager
  agent/        runtime → postgres_runtime → redis_runtime → traced_runtime
                workflow, hitl, recovery
  rca/          rca_core, incident_mock_data
  tools/        MCP servers/clients, tool_config, stderr launcher
  rag/          ingestion/embedding/retrieval/reranking/generation
  memory/       memory_config, memory_store, memory_retriever
  storage/      postgres_store, redis_store
  telemetry/    observability, trace_callback, trace_report
evaluation/     独立评分模块
tests/          原有12组回归与夹具
scripts/        原运维/测试/打包入口 + 包结构专项探针
docs/           architecture/deployment/testing/security
  release/      保留原历史发布与审计材料
  refactor/     本次5份报告
verification/   历史证据 + refactor/本次证据
```

API 没有新增第二个入口。没有新增依赖、框架或服务。公开合成 documents 保持不变，生成索引被 Git 和 Release 允许清单排除。

## 文件数量

重构前 Git 跟踪文件 101 个，其中根目录 Python 模块 43 个；43 个全部迁移，根目录 Python 业务模块变为 0 个。另有9份文档迁移、10个空包初始化文件及专项验证和报告/日志新增。最终交付文件数量以根目录 `RELEASE_FILES.json` 为准（该清单在所有报告完成后生成）。源码迁移没有通过删除功能减少文件数量。

最终允许交付文件 194 个（包含新增复验证据）；根目录业务Python文件0个。
