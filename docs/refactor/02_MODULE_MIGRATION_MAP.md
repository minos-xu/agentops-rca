# 模块迁移表

保留类名、函数名、协议和核心实现；测试导入、mock.patch、源码读取及运维字符串同步迁移。

| 原公开路径 | 新路径 | 主要类 / 函数 |
|---|---|---|
| `answerability.py` | `app/rag/answerability.py` | `judge_answerability`, `check_results_answerability`, `build_context`, `evaluate_answerability` |
| `api_routes.py` | `app/api/routes.py` | `MessageInput`, `ApprovalInput`, `create_app` |
| `bm25_store.py` | `app/rag/bm25_store.py` | `build_bm25_store`, `save_bm25_store`, `load_bm25_store` |
| `chunker.py` | `app/rag/chunker.py` | `tokenize`, `split_by_paragraph` |
| `config.py` | `app/core/config.py` |  |
| `context_manager.py` | `app/core/context_manager.py` | `ContextBudgetError`, `split_user_turns`, `validate_tool_pairs`, `flatten_turns`, `prepare_llm_context` |
| `deployment_config.py` | `app/core/deployment_config.py` | `environment_file`, `load_environment`, `data_directory`, `mcp_environment` |
| `embedder.py` | `app/rag/embedder.py` | `embed_text`, `embed_texts` |
| `embedding_store.py` | `app/rag/embedding_store.py` | `load_embedding_store`, `save_embedding_store` |
| `eval_dataset.py` | `app/rag/eval_dataset.py` |  |
| `filters.py` | `app/rag/filters.py` | `match_metadata` |
| `generator.py` | `app/rag/generator.py` | `build_context`, `build_sources`, `generate_answer` |
| `hitl.py` | `app/agent/hitl.py` | `ApprovalError`, `make_proposal`, `approval_decision`, `SimulationAudit` |
| `incident_mock_data.py` | `app/rca/incident_mock_data.py` | `list_incidents`, `case_exists`, `describe_incident`, `query_telemetry` |
| `ingest.py` | `app/rag/ingest.py` | `delete_document`, `calculate_hash`, `main` |
| `loader.py` | `app/rag/loader.py` | `load_document`, `load_documents` |
| `main.py` | `app/main.py` | `unavailable`, `create_recovery_app` |
| `mcp_stdio_launcher.py` | `app/tools/mcp_stdio_launcher.py` | `RedactedStderr`, `main` |
| `mcp_tool_runtime.py` | `app/tools/mcp_tool_runtime.py` | `MCPToolRuntime` |
| `memory_config.py` | `app/memory/memory_config.py` | `print_memories` |
| `memory_retriever.py` | `app/memory/memory_retriever.py` | `SemanticMemoryRetriever` |
| `memory_store.py` | `app/memory/memory_store.py` | `MemoryStore` |
| `observability.py` | `app/telemetry/observability.py` | `TraceContext`, `_utc_now`, `_safe_int`, `exception_status`, `ObservabilityCollector` |
| `observability_mcp_client.py` | `app/tools/observability_mcp_client.py` | `discover_observability_tools`, `_extract_json_result`, `query_observability_tool` |
| `observability_mcp_server.py` | `app/tools/observability_mcp_server.py` | `_read`, `get_service_metrics`, `search_logs`, `query_traces`, `get_service_topology` |
| `postgres_runtime.py` | `app/agent/postgres_runtime.py` | `PostgresAgentOpsRuntime` |
| `postgres_store.py` | `app/storage/postgres_store.py` | `SessionRepository`, `PostgresSimulationAudit` |
| `rag_mcp_server.py` | `app/tools/rag_mcp_server.py` | `rag_query` |
| `rag_pipeline.py` | `app/rag/rag_pipeline.py` | `run_rag` |
| `rca_core.py` | `app/rca/rca_core.py` | `RCAValidationError`, `_str`, `_require_str`, `_require_strings`, `make_evidence_catalog`, `has_observed_mechanism_signal`, `validate_rca`, `insufficient_report`, `render_report` |
| `recovery.py` | `app/agent/recovery.py` | `classify_error`, `bounded_call` |
| `redis_runtime.py` | `app/agent/redis_runtime.py` | `RateLimitProblem`, `RedisPostgresAgentOpsRuntime` |
| `redis_store.py` | `app/storage/redis_store.py` | `Lesson57RedisStore` |
| `reranker.py` | `app/rag/reranker.py` | `rerank` |
| `retriever.py` | `app/rag/retriever.py` | `cosine_similarity`, `get_candidate_vector_ids`, `retrieve_prefilter`, `retrieve` |
| `runtime.py` | `app/agent/runtime.py` | `APIProblem`, `summarize_state`, `AgentOpsRuntime` |
| `tool_config.py` | `app/tools/tool_config.py` |  |
| `trace_callback.py` | `app/telemetry/trace_callback.py` | `TraceCallback` |
| `trace_report.py` | `app/telemetry/trace_report.py` | `main` |
| `traced_runtime.py` | `app/agent/traced_runtime.py` | `InstrumentedAgentOpsRuntime` |
| `utility_mcp_server.py` | `app/tools/utility_mcp_server.py` | `calculator`, `get_weather` |
| `vector_store.py` | `app/rag/vector_store.py` | `create_index`, `save_index`, `load_state`, `load_index`, `add_vectors`, `remove_vectors` |
| `workflow.py` | `app/agent/workflow.py` | `AgentState`, `latest_question`, `normalize_plan`, `tracked_chat_completion`, `create_graph`, `main` |

## 文档迁移

- `ARCHITECTURE.md` → `docs/architecture.md`
- `DEPLOYMENT.md` → `docs/deployment.md`
- `TESTING.md` → `docs/testing.md`
- `SECURITY_AND_PUBLICATION_CHECK.md` → `docs/security.md`
- `FILE_INVENTORY.md` → `docs/release/FILE_INVENTORY.md`
- `FINAL_GITHUB_AUDIT.md` → `docs/release/FINAL_GITHUB_AUDIT.md`
- `GITHUB_PUBLICATION_CHECKLIST.md` → `docs/release/GITHUB_PUBLICATION_CHECKLIST.md`
- `GITHUB_PUBLICATION_REPORT.md` → `docs/release/GITHUB_PUBLICATION_REPORT.md`
- `RELEASE_MANIFEST.md` → `docs/release/RELEASE_MANIFEST.md`

## 引用变更

静态导入统一为 app.*；mock.patch 使用完整模块名。测试快照复制 app/，Trace 源码检查使用 app/ 下的相对路径；Uvicorn 唯一入口 app.main:app；index 使用 python -m app.rag.ingest；MCP 使用 python -m app.tools.*。MODULE_DEPENDENCIES.json 和 SOURCE_MAPPING.json 已更新，后者保留原始学习项目来源并增加 previous_public_path。历史报告显式标记旧路径，未抹除历史验证结果。
