> 历史发布证据：以下内容保留发布时状态与旧路径。当前包结构及复验见 [重构报告](../refactor/05_REFACTOR_FINAL_DECISION.md)。

# AgentOps GitHub 发布报告

> 本文记录上一阶段的验收。当前发布状态见 [最终发布审计](FINAL_GITHUB_AUDIT.md)。

上一阶段结论为 **READY TO PUBLISH**。独立 `agentops-rca-public/` 是公开候选目录。仅在发行前清单完成后将该目录提交到新的 GitHub 仓库。审计依据、构建和验证均针对该副本，未配置远程仓库。

## 结构与修改范围

```text
agentops-rca-public/
├── main.py, api_routes.py, workflow.py, rca_core.py, hitl.py
├── *_runtime.py, *_store.py, observability.py, recovery.py
├── *_mcp_server.py, observability_mcp_client.py, rag_pipeline.py
├── evaluation/          # 评分、鲁棒性和回归评测模块
├── tests/               # 12 组测试脚本及接线夹具
├── scripts/             # 启停、测试、模型校验、验收、打包
├── deploy/              # Redis 配置和外部模型校验清单
├── documents/           # 本次新编写的合成知识库
└── verification/        # 经筛选的验证摘要及测试结果
```

- [逐文件映射、保留和排除清单](FILE_INVENTORY.md) 与 [修改原因](../../SOURCE_MAPPING.json)。[部署与应用调用链](../architecture.md) 和 [机器可读依赖关系](../../MODULE_DEPENDENCIES.json)。
- 将 Lesson 命名改为模块职责，保留类名、函数接口和业务逻辑。`tool_config` 和 `memory_config` 只提取被现有运行代码引用的设置、Prompt 和辅助函数。MCP 子进程按项目相对路径启动。应用的状态目录名、Trace 文件名和 HTTP 接口保留兼容语义。
- 操作脚本改为依赖用户激活的 Conda，默认 Compose 项目名和端口独立。`index` 从公开合成文档本地复建 RAG 索引。离线模式覆盖 SDK 实际使用的两个 HTTPX 传输。测试改从 `tests/` 装载，保留原断言与临时 FaultSaver 兼容适配。
- 对最初 OSV 命中的约束做了独立安全更新。升级 `certifi`、`filelock`、`mcp`、`mcp-types`、`PyJWT`、`opentelemetry-api` 和 `setuptools`；用隔离 Python 环境中的升级发行包复跑验收。原 Conda 环境未被升级。

## 安全与许可证

允许清单排除了真实配置、凭据、原知识库、备份、模型、旧日志、旧 ZIP、历史二进制索引与运行数据。对候选文件做实际凭据精确匹配和上下文审查。Git 历史在本工作区不存在，无法核对其他来源的历史。原历史数据库安装脚本含与本机开发配置匹配的密码，建议手动轮换，公开副本已排除。其他凭据若曾分享，按各自服务流程轮换。 [安全检查](../security.md)

基于用户对公开权利的确认，项目采用 MIT，署名使用 `AgentOps contributors`。外部依赖、基础镜像和模型分别依照其上游授权。 [MIT 许可证](../../LICENSE) · [第三方说明](../../THIRD_PARTY_NOTICES.md)

## 重新验证的范围

- **12/12 组离线测试脚本**，包括原有 10 组及评分、鲁棒性两组。测试在临时源码快照运行，以模拟依赖和故障验证 RCA、HITL、Trace 与恢复等业务行为。
- **真实独立基础设施**。Compose 渲染、Redis 构建、FastAPI 启动、实际 PostgreSQL/Redis 健康、HTTP 建会话与 Redis 429、并发 Lua 限流、重启后同一 Session/Checkpoint/探针消息恢复。另验证实际 MCP 工具发现、Utility 和 Observability 工具调用、RAG MCP 无证据分支、本地 FAISS 检索与重排。
- **依赖安全**。Python 约束最终查询 OSV，119 个版本未返回匹配公告。`pip check` 与离线安装约束 dry run 检查通过。完整的基础镜像和操作系统漏洞盘点未执行。
- **本地打包验证**。ZIP 逐文件匹配允许清单，解压后 CLI 可用，临时空 Git 仓库的默认纳入清单一致。
- **原项目保护**。按 SHA-256 复验原目录的审计文件。验收使用新 Compose 项目、回环端口与新卷，停止测试服务后保留测试数据。没有向旧数据库或 Redis 发请求，没有调用 DeepSeek。

测试输出见 [验证证据](../../verification)。本次模型与容器均在已有 Linux 主机复用，Python 安全修补在隔离环境覆盖原基线；尚未在第二台全新服务器验证全套安装。基础设施探针不是生产 RCA。在线模型生成、RAG 最终回答和生产运行条件本次未验证。

## 公开仓库与求职展示

- 仓库名建议 `agentops-rca`。
- 简介建议 “Evidence-driven RCA Agent with FastAPI, LangGraph, MCP, and durable human approval for synthetic incidents.”
- 简历可写 “实现基于 FastAPI、LangGraph 和 MCP 的证据驱动故障调查 Agent，支持 PostgreSQL Checkpoint 恢复、HITL 模拟审批、Redis Lua 原子限流及 Trace。将核心链路和异常处理纳入 12 组离线回归，并以独立 Compose 环境验收会话重启恢复。”
- 演示读图优先走事故报告、审批中断与恢复、同一请求 Trace。引用合成数据和验收范围，避免用课程样本声称生产准确率。

发布前按 [人工检查清单](../security.md) 核对署名、暂存文件和仓库历史。不要把运行态配置和个人记录加入公开仓库。
