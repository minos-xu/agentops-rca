# 架构设计依据：源码与验证审计

审计基线：`main / 4313fe1`。本次仅文档工作，不运行应用、不调用API、不连接数据库。本表区分实现、独立验证和同一真实LLM链路验收。

- **A — Implemented**：源码存在对应职责与调用边。
- **B — Independently verified**：引用已有离线、本地计算、STDIO或真实基础设施证据，按各自范围描述。
- **C — Live LLM E2E verified**：必须由同一正式HTTP会话证明真实推理、工具/状态与诊断输出；最新结果为BLOCKED，不从A/B推定C。

## 核心审计矩阵

| Module / capability | A：实现与依据 | B：现有独立证据 | C：当前真实LLM链路 |
|---|---|---|---|
| FastAPI | `app/main.py:create_recovery_app` → `api/routes.py:create_app`；/messages先限流后ask | 历史真实HTTP Session与429；离线输入/故障验证 | 未完成 |
| Traced / Agent Runtime | `traced_runtime` → `redis_runtime` → `postgres_runtime` → `runtime`；lifespan start/close | Runtime启动与12组回归 | 未完成 |
| LangGraph / Agent State | `workflow.py:AgentState/create_graph`；事故与普通问答分支 | 离线真实图+Fake LLM；业务AST一致性 | 未完成 |
| DeepSeek integration | Runtime构造AsyncOpenAI；RAG构造同步Client | 当前项目Key缺失，最近真实调用0次；未验证官方当前模型可用性 | **BLOCKED** |
| Observability MCP | 真实Client.call_tool，四类只读合成观测，严格验证incident/tool/synthetic | 独立STDIO发现与四工具调用 | 未被真实LLM驱动验证 |
| Utility MCP | MCPToolRuntime路由calculator/get_weather | 独立STDIO发现与calculator调用 | 未被真实LLM驱动验证 |
| RAG MCP / retrieval | chat的rag_query → 检索/重排 → LLM资料判断/按需生成 | Server发现、真实本地Embedding/FAISS/Reranker；空证据Mock | 未完成；INC分支本就不调用RAG |
| Long-term Memory | retrieve_memory节点调用SemanticMemoryRetriever；历史提示不算当前证据 | 历史Runtime初始化；不能由此声称已验证真实会话召回质量 | 未完成 |
| HITL | prepare_proposal条件门槛 → interrupt → Command同线程恢复 | 离线中断/恢复与安全规则；历史真实HTTP无待审批409 | 真实LLM触发未覆盖 |
| PostgreSQL | Session映射、AsyncPostgresSaver Checkpoint与模拟审计 | 历史真实会话/重启/新卷恢复 | 同真实LLM请求的状态未覆盖 |
| Redis | 静态案例TTL缓存、消息Lua计数，故障时限流关闭 | 历史真实缓存、并发Lua、HTTP429 | 同真实LLM请求未覆盖 |
| Collector / Trace | request、callbacks、LLM/tool span；finally JSONL | 离线插桩与历史真实HTTP409落盘，后者0次LLM | 真实DeepSeek Trace未覆盖 |
| Deployment | manage脚本 → 宿主机Uvicorn + Compose PG/Redis | 历史独立资源启停/备份恢复 | 不能替代真实诊断E2E |

## 关键源码关系

| Relationship | Code evidence | Diagram decision |
|---|---|---|
| HTTP → Runtime → Graph | `api.routes.send_message`、`runtime.ask`的`graph.ainvoke` | 主请求粗线，不将只读查询误画为必经Graph |
| Graph → DeepSeek | `tracked_chat_completion`及planner/structured_rca/llm节点 | 外部Provider，标记Live E2E pending |
| Incident → MCP | `collect_evidence_node`调用`query_observability_tool` | 事故证据分支，非全部工具串联 |
| Chat → RAG / Utility | llm解析tool_calls；tools节点生成ToolMessage再回llm | 条件分支；不把RAG画进INC事故主链 |
| RAG → local / external | `rag_pipeline.run_rag`、answerability与generator | 本地检索单独节点；判断/生成连外部API |
| Memory → graph context | `retrieve_memory_node`检索后拼memory_context | 历史启发；不混作观测或权威证据 |
| HITL → durable state | `interrupt`与Saver；`runtime.approve`的Command | 先返回pending，另一个HTTP决定同线程恢复 |
| State / trace support | PG Saver、RedisStore、TraceCallback与finally | 辅助存储/观测线，不作为LLM推理步骤 |

## 不能从图中推导的结论

1. 所有工具并非每次请求必经。INC分支的Planner是JSON计划，不是原生tool_calls循环。
2. RAG可被普通问答调用，不代表最近INC测试已实际使用它。
3. expected_cause只供模拟评测，不发给模型；Observability Server没有生产监控连接。
4. 批准产生模拟审计，绝不意味着真实修复、验证恢复或生产权限。
5. Trace不是跨进程分布式追踪：MCP内部Collector不会自动汇聚，RAG内部LLM用量不受父请求计数完整覆盖。
6. PostgreSQL、Redis、Trace已有真实基础设施记录，但最近真实LLM E2E仍BLOCKED。

## 证据入口

- [最新E2E结论](../e2e/05_FINAL_E2E_DECISION.md)与[本轮凭据门禁记录](../../verification/e2e/blocked-preflight.json)：0次真实调用、12/12回归及独立探针。
- [完整回归对照](../refactor/04_REGRESSION_RESULTS.md)：历史真实基础设施与离线测试分开记录。
- [真实工具探针](../../scripts/check_package_layout.py)、[正式测试入口](../../scripts/run_tests.py)：明确独立RAG/MCP能力和Mock边界。
- [部署与数据保留](../deployment.md)、[安全说明](../security.md)：宿主机应用、外部权重、独立卷、回环端口。

本审计没有以模块命名代替源码追踪，也未修改旧报告或重新声明它们为本轮运行结果。
