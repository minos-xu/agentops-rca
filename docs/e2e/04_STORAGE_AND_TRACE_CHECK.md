# 状态、存储与 Trace 检查

## 本轮真实Agent范围

凭据门禁阻断在线流程。没有新建数据库/Redis容器，没有连接任何数据库，没有创建在线E2E Session、Checkpoint或审批记录；没有清空或删除持久化数据。

| 对象 | 代码接入位置 | 本轮在线Agent实测 |
|---|---|---|
| Session | postgres_runtime.create_session → SessionRepository.insert | 未执行 |
| Checkpoint | AsyncPostgresSaver；runtime.ask中的graph.ainvoke / aget_state | 未执行 |
| PostgreSQL | saver、Session映射、模拟审计 | 未连接，无新增真实Agent状态 |
| Redis | enforce_message_rate_limit原子Lua；cached_cases TTL缓存 | 未连接，无本轮真实HTTP限流计数 |
| Trace | traced_runtime.ask/approve → run_scope → finally _save_trace | 未产生真实DeepSeek请求Trace |
| HITL | prepare_proposal → human_approval/interrupt；同thread恢复 | 仅离线回归覆盖，真实LLM触发未覆盖 |

## 源码确认的观察方式

成功响应的Usage由tracked_chat_completion转为llm_usage事件，记录prompt/completion/total_tokens。LLM尝试、MCP调用、graph节点和request span可通过trace_id关联；session_id/incident_id在events中，JSONL摘要并非顶层session_id。API响应也没有新增顶层trace_id字段，不虚构客户端已拿到Trace ID。

Collector最多5000事件且进程内，不自动汇总MCP子进程。RAG同步Client的内部LLM请求没有经过Agent tracked_chat_completion，不能只用父Trace的llm_call_count作为跨进程全局计费请求数。这是预算和统计覆盖边界，不能用Mock测试抹平。

## 本轮安全测试与历史记录

本轮已执行/最终结果见05报告：正式12组离线回归、既有本地RAG、真实STDIO探针、模块导入。回归使用临时快照、占位Key、禁TCP连接，PG/Redis异常由替身注入；它们不等价于本轮真实数据库验收。RAG本地Embedding/FAISS/Reranker是实际计算，空证据分支按既有探针Mock。MCP用真正子进程通信，但数据为合成遥测。

此前 `verification/refactor/infra-*.txt`、restore.json、trace.json等是上轮真实基础设施证据。没有作为本轮执行结果，也没有为了缺Key而重复操作旧卷。没有修改其他项目、schema、Checkpoint格式、Memory或持久化策略。

## 后续隔离要求

Key配置及全局预算门禁就绪后，使用新的agentops-rca-*项目名、空数据库卷、未占用回环端口和独立AGENTOPS_DATA_DIR；只保存本次合成Case，数据保留。只读核对session/thread映射、checkpoint message/report、Redis限流计数、trace的LLM/工具/Token事件。HITL待审批仅验证中断，默认不自动批准；必要的拒绝路径依原业务规则执行。
