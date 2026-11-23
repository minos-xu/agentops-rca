# Agent 真实端到端诊断结果

结论：**BLOCKED**。当前项目缺少DEEPSEEK_API_KEY，没有启动正式在线API或创建E2E Session，没有向DeepSeek发出请求。以下案例与链路是源码审计及后续单案例验收范围，不是本轮执行日志。

## 选定的公开合成案例

INC-001（Payment数据库连接池耗尽）。只使用 `app/rca/incident_mock_data.py` 的公开合成数据。其模拟真值expected_cause为Payment数据库连接池耗尽；仅用于最终对照，不写进用户问题、LLM上下文或MCP响应。

只读证据工具为get_service_metrics、search_logs、query_traces，以及可选get_service_topology。现有query_observability_tool检查事故/工具匹配及synthetic，并拒绝expected_cause字段泄露。

## 正式请求与预期验收

正式路径必须是 `POST /api/v1/sessions` → `POST /api/v1/sessions/{sid}/messages`，body只含公开问题 `{"message":"请基于只读模拟遥测调查 INC-001，列出证据与仍需验证的事项。"}`。不是直接调用create_graph或ChatCompletion代替HTTP。

应核对 `/report` 的incident_id、validation、diagnosis_status、hypotheses、supporting_evidence_ids/counter_evidence_ids和机制证据。若满足既有提案条件，应看到pending_approval与human_approval中断。安全字段safe_to_remediate和recovery_verified必须保持false；不得报告真实系统恢复。

Session ID、Trace ID、HTTP状态、真实诊断文本、模型判断和真值匹配本轮均无结果，不提供伪造的自然语言诊断示例。

## 本轮覆盖矩阵

| 环节 | 实际结果 |
|---|---|
| 真实DeepSeek推理与Agent消费其结果 | 未执行 |
| 正式HTTP诊断请求 | 未执行 |
| 事故Planner JSON → MCP收证 → RCA生成 | 源码证实接入；本轮真实E2E未执行 |
| 三类MCP | 本轮独立STDIO探针执行；不计为真实LLM驱动E2E参与 |
| RAG | 本轮独立本地检索探针；没有真实Agent触发rag_query |
| PG/Redis/Checkpoint | 未在本轮真实Agent执行中覆盖 |
| HITL | 原离线测试覆盖；真实LLM驱动中断未覆盖 |
| 用例正确率 | 不计算；既无实际预测，也不能从单例推断整体准确率 |

INC路径由Planner JSON给出工具计划，再由Python白名单执行MCP，RCA使用工具证据目录。它本身不执行RAG普通问答循环。后续即使INC-001诊断成功，也不应同时声称原生ReAct循环或RAG端到端已通过。

## 阻塞与修复范围

阻塞根因为本项目授权Key缺失，不是已经证明的模型/Agent代码错误。没有为了通过验收替换LLM、改Prompt、跳过校验、硬编码答案或重新拼接业务流程。未定位到需要修改业务逻辑的运行故障，因此未进行业务修复。
