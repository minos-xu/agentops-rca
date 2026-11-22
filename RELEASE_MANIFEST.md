# 公开发布文件清单

审计日期为 2026-11-22。本目录按 [允许清单](RELEASE_FILES.json) 发布。

- 文件数 **101**。文件内容总体积 **393021 字节**，含本清单，不计目录与 Git 元数据。
- 最大文件 `workflow.py` 为 32817 字节。候选内容均为文本。
- 候选无 `.git`、历史提交或远程配置。对临时空 Git 仓库暂存的实际路径和本地 ZIP 成员逐项做一致性检查。

## 排除范围

真实环境配置、服务凭据、私有/旧课程文档、原始 Git 历史、会话数据、数据库与备份、Redis 运行文件、Memory、Trace、部署和实验日志、模型权重、索引和 pickle、Conda 环境、缓存、旧 ZIP 与其他二进制。保留合成数据源及脱敏验证摘要。 [文件归类与原名映射](FILE_INVENTORY.md)

## 验收命令与结果

下列命令在隔离快照使用 `agent-dev` 派生解释器。真实服务验收使用全新 Compose 项目及回环端口。

| 命令或探针 | 结果 |
|---|---|
| `bash scripts/manage.sh test --output-dir <audit-log-dir>` | 12/12 脚本组通过。 |
| `bash scripts/manage.sh init`、`bash scripts/manage.sh compose config --quiet`、`bash scripts/manage.sh index` | 生成隔离配置、Compose 解析、重建 4 个 RAG 文件通过。 |
| `bash scripts/manage.sh up --offline`、`bash scripts/manage.sh health`、`bash scripts/manage.sh acceptance seed --state .deployment/probe.json` | PostgreSQL、Redis、HTTP、会话、缓存与限流探针通过。 |
| `bash scripts/manage.sh stop` 后重启，`bash scripts/manage.sh acceptance verify --state .deployment/probe.json` | 同一 Session、Checkpoint ID 和合成消息恢复成功。最终停机保留测试卷。 |
| 本地模型文件校验与目录外 MCP 探针 | 模型 19 个文件校验、本地 FAISS 检索和重排、三个 STDIO 服务发现及工具调用通过。 |
| `python -m pip check`、`python -m pip install --dry-run --no-index -r requirements.txt` | 已装依赖一致，离线 dry run 通过。 |
| 临时 `git init` / `git add -A` / `git ls-files`，`python scripts/package_release.py --output <audit-zip-path>` | 暂存与打包文件均和允许清单一致。 |

[离线与依赖证据](verification/final-audit.json) · [真实基础设施输出](verification/final-audit-runtime.txt)

## 关键文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| `README.md` | `d74b9f11f4ef412806333a258b8cc63daa347ae159baa5721d4fbbb12e3d909a` |
| `LICENSE` | `de2abe6735b18dfe399a8ee6cd9cdcc06dc2e5bb677b5b829835c90460bbd364` |
| `.gitignore` | `5f843c7ab68ecb487237befaca05a2bd49643d77227f2ce5848e7583cd18fd80` |
| `.env.example` | `21b8a3d8a54a020a916499f3018faae81be5d4657cb8149536ea04bcb955623c` |
| `.env.docker.example` | `7585984e97fdc12b8d5dadf2ea438640e1770a29950375d4e1b93555baaa567b` |
| `main.py` | `b10870da138762481d3a47308f5adfacd8f394cfac9dbf88ab14a56b87cc6a02` |
| `workflow.py` | `a521658e1843a0a85c01e2ea3bc46e8177323e5c4efb39b0b07aaae42abb8f5f` |
| `rca_core.py` | `b81ba2c0317c6a8464e16d9a9766d73c56718677360fe7eec0c4bcd9f21fe74b` |
| `hitl.py` | `0ba4a3e98cb8064684ebc448da93e9e760aa62c562100841432a810b7a204422` |
| `observability.py` | `11912b30e077d59deb7f124563a47ed95d982bd0cd28951fa73535972e1d578e` |
| `recovery.py` | `79f473a53f8ff1bac6ec83a61fdf31cb9af6c06fad7572ea47058815f55e8fa0` |
| `scripts/manage.sh` | `ac4043f0edf5c8336f836314a28c18bac0885233fbad64deded909906efb676b` |
| `docker-compose.yml` | `d8d814f55a966312e4debe297a3c2dbbd2f7d5a43112482b309c47dc68248ac1` |
| `Dockerfile` | `4d6002ccb80649690336297031023c4ea31fea5a92a7c954659f58450f89eb87` |
| `requirements.txt` | `71e6fe0e7926a46a3840517616d5f19106272e52509a810728bccc591ae2c59f` |
| `requirements.lock.txt` | `00f535fac899b59fd5545932eaff2986a5d7484c336067dae88fc8b3c388c492` |
| `environment.yml` | `ede14b341dd60797072cf97834890a22331ae603efd044a64e0fac4bbb0fee5e` |
| `deploy/models.manifest.json` | `a1c63336b266e25fd4a4063f4f28b6b8a14d1e3cd6a2883c7910ee9b469bdadc` |
| `RELEASE_FILES.json` | `e8c95185ab991af70c63e60d0baacb2f7cabe36216c77c7659d91b6682458fb0` |
| `verification/final-audit.json` | `b0dbc21a381b9d440da787447f6b4bd6505cfff9250615be01f0a7bd1811b762` |
| `verification/final-audit-runtime.txt` | `ce86547aaf2afe115a6ce3d03b9905b54b7013d45510f0366213b1059797326a` |

## 完整文件列表

- `.dockerignore`
- `.env.docker.example`
- `.env.example`
- `.gitignore`
- `ARCHITECTURE.md`
- `DEPLOYMENT.md`
- `Dockerfile`
- `FILE_INVENTORY.md`
- `FINAL_GITHUB_AUDIT.md`
- `GITHUB_PUBLICATION_CHECKLIST.md`
- `GITHUB_PUBLICATION_REPORT.md`
- `LICENSE`
- `MODULE_DEPENDENCIES.json`
- `README.md`
- `RELEASE_FILES.json`
- `RELEASE_MANIFEST.md`
- `SECURITY_AND_PUBLICATION_CHECK.md`
- `SOURCE_MAPPING.json`
- `TESTING.md`
- `THIRD_PARTY_NOTICES.md`
- `answerability.py`
- `api_routes.py`
- `bm25_store.py`
- `chunker.py`
- `config.py`
- `context_manager.py`
- `deploy/models.manifest.json`
- `deploy/redis/redis.conf`
- `deployment_config.py`
- `docker-compose.yml`
- `documents/demo_ops_manual.txt`
- `embedder.py`
- `embedding_store.py`
- `environment.yml`
- `eval_dataset.py`
- `evaluation/__init__.py`
- `evaluation/eval_regression.py`
- `evaluation/eval_robustness.py`
- `evaluation/eval_scoring.py`
- `filters.py`
- `generator.py`
- `hitl.py`
- `incident_mock_data.py`
- `ingest.py`
- `loader.py`
- `main.py`
- `mcp_stdio_launcher.py`
- `mcp_tool_runtime.py`
- `memory_config.py`
- `memory_retriever.py`
- `memory_store.py`
- `observability.py`
- `observability_mcp_client.py`
- `observability_mcp_server.py`
- `postgres_runtime.py`
- `postgres_store.py`
- `rag_mcp_server.py`
- `rag_pipeline.py`
- `rca_core.py`
- `recovery.py`
- `redis_runtime.py`
- `redis_store.py`
- `requirements.lock.txt`
- `requirements.txt`
- `reranker.py`
- `retriever.py`
- `runtime.py`
- `scripts/deployment_probe.py`
- `scripts/manage.py`
- `scripts/manage.sh`
- `scripts/package_release.py`
- `scripts/run_tests.py`
- `scripts/verify_models.py`
- `tests/fixtures/trace_api.py`
- `tests/test_error_classification.py`
- `tests/test_eval_regression.py`
- `tests/test_eval_robustness.py`
- `tests/test_eval_scoring.py`
- `tests/test_hitl.py`
- `tests/test_observability.py`
- `tests/test_postgres_store.py`
- `tests/test_rca.py`
- `tests/test_recovery.py`
- `tests/test_redis_degradation.py`
- `tests/test_trace_wiring.py`
- `tests/test_workflow_interrupt.py`
- `tool_config.py`
- `trace_callback.py`
- `trace_report.py`
- `traced_runtime.py`
- `utility_mcp_server.py`
- `vector_store.py`
- `verification/dependency-audit.json`
- `verification/final-audit-runtime.txt`
- `verification/final-audit.json`
- `verification/model-checks.txt`
- `verification/offline-regression.json`
- `verification/publication-scan.json`
- `verification/recovery-tests.txt`
- `verification/runtime-smoke.txt`
- `workflow.py`
