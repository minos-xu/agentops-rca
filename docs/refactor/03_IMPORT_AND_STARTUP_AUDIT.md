# 导入、启动与数据路径审计

## FastAPI 与 Runtime

`app.main:app` → `app.api.routes.create_app(InstrumentedAgentOpsRuntime)`。继承链为 `app.agent.traced_runtime` → `redis_runtime` → `postgres_runtime` → `runtime`。start/close 的调用顺序、AsyncExitStack 释放顺序、Saver.setup、Session 加载、审计、Redis、graph 组合及已知依赖503异常处理均保留。

## MCP STDIO

- RAG：同一 `sys.executable -m app.tools.mcp_stdio_launcher app.tools.rag_mcp_server`。
- Utility：同一解释器 `-m app.tools.utility_mcp_server`。
- Observability：同一解释器 `-m app.tools.observability_mcp_server`；正式与备用 Runtime/CLI 一并修正。
- cwd 明确为稳定项目根，父调用方可来自 /tmp。模块版 launcher 使用 run_module；仅 stderr 脱敏，stdout 不包装，保持 JSON-RPC。
- 白名单配置、占位Key与离线回环生成地址保持不变，不调用真实 DeepSeek。

## RAG 与数据

`app/core/deployment_config.py` 使用 `Path(__file__).resolve().parents[2]` 解析项目根。documents、vector.index、metadata.json、embedding_store.pkl、bm25_store.pkl 读写保持在原公开项目根，格式和算法不变；不再依赖 shell cwd。`bash scripts/manage.sh index` 调用包模块重建公开合成索引，索引不提交。

AGENTOPS_ENV_FILE 默认仍为项目根.env；AGENTOPS_DATA_DIR 默认仍为根data，部署仍为.deployment/data；Memory 子目录 lesson49_agentops 与 Trace 的 lesson62_traces.jsonl 保留。模型路径由原变量/HF缓存解析。没有迁移已有私有文件或数据库数据。

## 正式测试与发布

run_tests 复制完整 app/、evaluation/、12组测试及 trace_api 夹具；不复制真实.env、索引、运行数据。保留网络连接禁止、strict msgpack、FaultSaver共享开关临时适配与所有断言。新的 patch 路径使用 app.*。

动态引用检查覆盖 import/from、mock.patch、runpy、subprocess、python -m、__file__、Uvicorn字符串、源码检查与release清单。历史发布文档可保留旧模块名，但已标记历史，不能作为当前启动说明。

关键业务AST/提示词/原测试assert一致性见 verification/refactor/semantic-parity.json。所有模块真实导入结果见 imports.txt；完整依赖图见 MODULE_DEPENDENCIES.json。配置常量与进程入口路径的变化属于本次结构迁移范围，未顺手修复业务问题。
