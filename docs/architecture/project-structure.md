# 项目目录与职责

目录按运行职责组织。正式入口是 `app/main.py` 中的 `app.main:app`；不是 `app/app.main.py`，也没有第二个根目录应用入口。

```text
app/
├── main.py
├── api/
├── core/
├── agent/
├── rca/
├── tools/
├── rag/
├── memory/
├── storage/
└── telemetry/
scripts/     tests/     evaluation/
documents/   docs/      verification/
deploy/
```

| Directory | Responsibility / core modules | Boundary and relationships |
|---|---|---|
| `app/api/` | `routes.py`：FastAPI 路由、Pydantic 请求验证 | 调用 Runtime，不自行编排 RCA 或执行生产动作 |
| `app/core/` | `deployment_config.py`、`config.py`、`context_manager.py` | 稳定项目根、环境配置、模型参数与上下文预算；不是独立服务 |
| `app/agent/` | `workflow.py`、`runtime.py`、持久化/Trace Runtime、`hitl.py`、`recovery.py` | LangGraph 节点、状态与审批；使用工具、证据规则和存储适配 |
| `app/rca/` | `rca_core.py`、`incident_mock_data.py` | 验证当前事件证据与结构化报告；合成真值只供评测，不传给工具/模型 |
| `app/tools/` | `tool_config.py`、MCP clients/servers、`mcp_stdio_launcher.py` | 真实 STDIO、工具发现/路由与脱敏；不等同全部工具每次都会被调用 |
| `app/rag/` | `ingest.py`、`retriever.py`、`reranker.py`、`rag_pipeline.py` | 文档索引、检索、重排；answerability/生成需外部 LLM，由普通问答的 rag_query 可选触发 |
| `app/memory/` | `memory_store.py`、`memory_retriever.py`、`memory_config.py` | 跨会话历史提示与 FAISS；不能作为当前事故已确认的证据 |
| `app/storage/` | `postgres_store.py`、`redis_store.py` | Session/审计与缓存/限流适配；LangGraph Saver 另外负责 Checkpoint |
| `app/telemetry/` | `observability.py`、`trace_callback.py`、`trace_report.py` | 安全元数据、时间与用量；Collector 不跨进程汇聚，不是外部 tracing 平台 |
| `scripts/` | `manage.sh`、`manage.py`、`run_tests.py`、探针 | 复用既定运维和验收入口，不是业务模块 |
| `tests/` | 12 组离线脚本与夹具 | 隔离快照，保留 Mock/断网/严格序列化边界 |
| `evaluation/` | 独立评分、回归门槛和鲁棒性规则 | 不进入正式在线诊断，不可当作已验证生产准确率 |
| `documents/` | 公开合成知识库 | 本机生成根目录索引；只加载可信索引，不提交权重/pickle/FAISS 产物 |
| `deploy/` | Redis 配置与模型校验清单 | Compose 只管理 PostgreSQL / Redis，API 在宿主机 |
| `docs/` | 架构、部署、测试、安全与历史审计 | `architecture/` 保留图源；`e2e/` 明确真实调用边界 |
| `verification/` | 脱敏测试摘要与日志 | 证据不是在线数据源；保留不同验收阶段，不把历史记录冒充本轮执行 |

## 源码与数据分离

- 模型：本地离线目录 / Hugging Face 缓存，不随 Python 源文件移动。
- 知识库：`documents/`，生成的 `vector.index`、`metadata.json`、`embedding_store.pkl`、`bm25_store.pkl` 位于项目根。
- 私有配置：`.env` / `.env.docker`，不进入 Git，模板不包含真实凭据。
- 部署数据：`.deployment/data/`；兼容已有 `lesson49_agentops` 和 `lesson62_traces.jsonl` 名称。
- PostgreSQL 命名卷保存权威会话与 Checkpoint；Redis 只保存可重建缓存/限流窗口。

[总体架构](../architecture.md) · [源码审计](SOURCE_AUDIT.md) · [返回 README](../../README.md)
