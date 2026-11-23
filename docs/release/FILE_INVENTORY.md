> 历史发布证据：以下内容保留发布时状态与旧路径。当前包结构及复验见 [重构报告](../refactor/05_REFACTOR_FINAL_DECISION.md)。

# 文件清单与重命名

本次原目录审计覆盖 337 个常规文件。下表按原始路径列出保留、提取、改名或调整的全部来源文件。新增的公开文档、许可、合成知识库和测试结果见 `RELEASE_FILES.json`。

| 新路径 | 原路径 | 分类 |
|---|---|---|
| `.dockerignore` | `.dockerignore` | C. 部署与配套 |
| `.env.docker.example` | `.env.docker.example` | C. 部署与配套 |
| `.env.example` | `.env.example` | C. 部署与配套 |
| `Dockerfile` | `Dockerfile` | C. 部署与配套 |
| `answerability.py` | `answerability.py` | A. 正式运行源码 |
| `api_routes.py` | `lesson57_agentops_api.py` | A. 正式运行源码 |
| `bm25_store.py` | `bm25_store.py` | A. 正式运行源码 |
| `chunker.py` | `chunker.py` | A. 正式运行源码 |
| `config.py` | `config.py` | A. 正式运行源码 |
| `context_manager.py` | `context_manager.py` | A. 正式运行源码 |
| `deploy/models.manifest.json` | `deploy/models.manifest.json` | C. 部署与配套 |
| `deploy/redis/redis.conf` | `deploy/redis/redis.conf` | C. 部署与配套 |
| `deployment_config.py` | `deployment_config.py` | A. 正式运行源码 |
| `docker-compose.yml` | `docker-compose.yml` | C. 部署与配套 |
| `embedder.py` | `embedder.py` | A. 正式运行源码 |
| `embedding_store.py` | `embedding_store.py` | A. 正式运行源码 |
| `environment.yml` | `environment.yml` | C. 部署与配套 |
| `eval_dataset.py` | `eval_dataset.py` | A. 正式运行源码 |
| `evaluation/eval_regression.py` | `archive/files/lesson61_regression_core.py` | B. 自动化测试或评测 |
| `evaluation/eval_robustness.py` | `archive/files/lesson60_robustness_core.py` | B. 自动化测试或评测 |
| `evaluation/eval_scoring.py` | `archive/files/lesson59_eval_core.py` | B. 自动化测试或评测 |
| `filters.py` | `filters.py` | A. 正式运行源码 |
| `generator.py` | `generator.py` | A. 正式运行源码 |
| `hitl.py` | `lesson53_hitl_core.py` | A. 正式运行源码 |
| `incident_mock_data.py` | `incident_mock_data.py` | A. 正式运行源码 |
| `ingest.py` | `ingest.py` | A. 正式运行源码 |
| `loader.py` | `loader.py` | A. 正式运行源码 |
| `main.py` | `lesson63_agentops_api.py` | A. 正式运行源码 |
| `mcp_stdio_launcher.py` | `mcp_stdio_launcher.py` | A. 正式运行源码 |
| `mcp_tool_runtime.py` | `mcp_tool_runtime.py` | A. 正式运行源码 |
| `memory_config.py` | `lesson49_langgraph_agentops_memory.py` | A. 正式运行源码 |
| `memory_retriever.py` | `memory_retriever.py` | A. 正式运行源码 |
| `memory_store.py` | `memory_store.py` | A. 正式运行源码 |
| `observability.py` | `lesson62_observability.py` | A. 正式运行源码 |
| `observability_mcp_client.py` | `observability_mcp_client.py` | A. 正式运行源码 |
| `observability_mcp_server.py` | `observability_mcp_server.py` | A. 正式运行源码 |
| `postgres_runtime.py` | `lesson55_runtime.py` | A. 正式运行源码 |
| `postgres_store.py` | `lesson55_db.py` | A. 正式运行源码 |
| `rag_mcp_server.py` | `rag_mcp_server.py` | A. 正式运行源码 |
| `rag_pipeline.py` | `rag_pipeline.py` | A. 正式运行源码 |
| `rca_core.py` | `lesson52_rca_core.py` | A. 正式运行源码 |
| `recovery.py` | `lesson63_recovery.py` | A. 正式运行源码 |
| `redis_runtime.py` | `lesson57_runtime.py` | A. 正式运行源码 |
| `redis_store.py` | `lesson57_redis_store.py` | A. 正式运行源码 |
| `requirements.lock.txt` | `requirements.lock.txt` | C. 部署与配套 |
| `requirements.txt` | `requirements.txt` | C. 部署与配套 |
| `reranker.py` | `reranker.py` | A. 正式运行源码 |
| `retriever.py` | `retriever.py` | A. 正式运行源码 |
| `runtime.py` | `lesson54_runtime.py` | A. 正式运行源码 |
| `scripts/deployment_probe.py` | `scripts/lesson64_acceptance.py` | C. 部署与配套 |
| `scripts/manage.py` | `scripts/lesson64_manage.py` | C. 部署与配套 |
| `scripts/manage.sh` | `scripts/lesson64.sh` | C. 部署与配套 |
| `scripts/package_release.py` | `scripts/lesson64_package.py` | C. 部署与配套 |
| `scripts/run_tests.py` | `scripts/lesson64_regression.py` | C. 部署与配套 |
| `scripts/verify_models.py` | `scripts/lesson64_models.py` | C. 部署与配套 |
| `tests/fixtures/trace_api.py` | `archive/files/lesson62_agentops_api.py` | B. 自动化测试或评测 |
| `tests/test_error_classification.py` | `archive/files/test_lesson63_unit.py` | B. 自动化测试或评测 |
| `tests/test_eval_regression.py` | `archive/files/test_lesson61_regression_unit.py` | B. 自动化测试或评测 |
| `tests/test_eval_robustness.py` | `archive/files/test_lesson60_robustness_unit.py` | B. 自动化测试或评测 |
| `tests/test_eval_scoring.py` | `archive/files/test_lesson59_eval_unit.py` | B. 自动化测试或评测 |
| `tests/test_hitl.py` | `archive/files/test_lesson53_hitl.py` | B. 自动化测试或评测 |
| `tests/test_observability.py` | `archive/files/test_lesson62_observability.py` | B. 自动化测试或评测 |
| `tests/test_postgres_store.py` | `archive/files/test_lesson55_unit.py` | B. 自动化测试或评测 |
| `tests/test_rca.py` | `archive/files/test_lesson52_rca.py` | B. 自动化测试或评测 |
| `tests/test_recovery.py` | `archive/files/test_lesson63_recovery.py` | B. 自动化测试或评测 |
| `tests/test_redis_degradation.py` | `archive/files/test_lesson58_degradation.py` | B. 自动化测试或评测 |
| `tests/test_trace_wiring.py` | `archive/files/test_lesson62_integration_offline.py` | B. 自动化测试或评测 |
| `tests/test_workflow_interrupt.py` | `archive/files/test_lesson53_graph.py` | B. 自动化测试或评测 |
| `tool_config.py` | `lesson46_langgraph_multi_mcp.py` | A. 正式运行源码 |
| `trace_callback.py` | `lesson62_trace_callback.py` | A. 正式运行源码 |
| `trace_report.py` | `lesson62_trace_report.py` | A. 正式运行源码 |
| `traced_runtime.py` | `lesson62_instrumented_runtime.py` | A. 正式运行源码 |
| `utility_mcp_server.py` | `utility_mcp_server.py` | A. 正式运行源码 |
| `vector_store.py` | `vector_store.py` | A. 正式运行源码 |
| `workflow.py` | `lesson53_agentops_hitl.py` | A. 正式运行源码 |

逐文件改动原因见 `SOURCE_MAPPING.json`，静态导入闭包和动态入口见 `MODULE_DEPENDENCIES.json`。

## 排除项

| 原路径或类型 | 理由 |
|---|---|
| `.env`、`.env.docker`、`.deployment/` | 本机凭据、运行控制、探针与部署数据 |
| `data/`、`archive/files/data/`、`backups/`、`deployment_logs/` | 会话消息、Trace、备份和未经公开审阅的日志。公开副本只保留必要的脱敏验证摘要 |
| 原 `documents/`、`vector.index`、`metadata.json`、`*.pkl`、`embeddings.npy` | 原知识库及其派生索引不公开。通过新的合成文档与 `index` 重建 |
| `archive/` | 只选取上表必要的测试、评分源码和插桩夹具。其他课程版本、在线评测历史脚本和材料均排除 |
| `docs/second_project_audit/` | 其他项目调研，与运行无关 |
| `lesson64_deployment.zip` 及校验文件 | 旧交付，含历史材料和本机运行证据 |
| `__pycache__/`、模型权重、Conda、镜像、数据库卷 | 可再生或按部署手册独立准备，运行数据不随发布 |
| 原 README、旧交付/课程文档及旧打包脚本 | 由正式使用说明和基于允许清单的脚本替代 |

按原文件计数：
- C. 被替换的旧发布文档或脚本：8
- D. 历史课程或其他项目材料：89
- E. 原知识库及生成的索引：10
- E. 可再生缓存：37
- E. 敏感配置和运行数据：118
