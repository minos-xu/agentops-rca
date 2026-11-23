# AgentOps RCA 三图设计与发布审查

审查日期：2026-11-23。源码基线：本地 `main / 4313fe1` 及审计工作区。工作目录：`/home/ubuntu/project/agentops-rca-public`。

## 审查结论与发布标准

三张图已经完成源码核对、正式高清导出与实际 PNG 预览；README 已更新。**发布验收 PASS：用户已明确确认“只要内容和项目对应就可以直接推送到 GitHub”，取消参考图片比对作为发布前提，授权创建文档提交并推送 main。** 参考原图仍未提供，不声称完成了严格风格比对。

| 图 / 检查 | 源码与本地视觉 | 参考图严格对照 | 完整验收 |
|---|---|---|---|
| 01 系统分层架构 | PASS | 未验证：缺少参考图一 | PASS（按用户确认标准） |
| 02 RCA 请求 UML 时序 | PASS | 未验证：缺少参考图二 | PASS（按用户确认标准） |
| 03 项目目录树 | PASS | 未验证：缺少参考图三 | PASS（按用户确认标准） |
| 源码一致性 | PASS：静态审计范围 | 不适用 | PASS |
| 高清 SVG / PNG | PASS：矢量 SVG、2 倍 PNG | 不适用 | PASS |
| README 相对链接 | PASS：本地路径检查 | GitHub 远端展示未执行 | PASS（本地） |

原始文字附件中没有三张参考位图；三图依据文字要求完成。用户已接受以项目源码一致性为发布标准，因此缺少参考图不再阻止发布；参考图逐像素或严格风格匹配不属于此次已完成的验证。

## 参考风格分析及统一设计语言

以下只分析任务文字明确描述的风格，不声称已经看过参考图片。

1. 分层架构：横向色带、层名左置、矩形模块对齐、上下调用箭头；用蓝/紫/青/橙分别表达 API、编排、工具与推理、状态与观测。外部 Provider 单列，避免误认为部署容器。
2. UML 时序：横排 Participant、垂直虚线 Lifeline、实线请求/虚线返回、Activation、自调用和实际存在的 opt / alt / loop。用顶部边界区分 API 进程、STDIO 子进程、外部服务及 Compose 数据服务。
3. 目录结构：白底、树枝与缩进、蓝色粗体目录、普通等宽文件名、右侧灰色职责说明；只保留真实核心路径，不使用卡片或装饰图标。

三图统一使用 DejaVu Sans / Mono、深蓝标题、灰色辅助文字及一致的职责配色；无渐变、阴影、水印或在线绘图上传。

## 实际源码审计与图中对应关系

先核对应用入口、继承链、工作流及部署配置，再生成图。补充审计矩阵见 [SOURCE_AUDIT.md](SOURCE_AUDIT.md)，历史验证边界见 [最新 E2E 决策](../e2e/05_FINAL_E2E_DECISION.md)。

| 图中模块 / 关系 | 当前源码依据 | 绘图处理 |
|---|---|---|
| FastAPI 入口与请求校验 | `app/main.py:create_recovery_app`；`app/api/routes.py:create_app/MessageInput/send_message` | 图一 HTTP 入口；图二先校验和消息限流，再 traced ask |
| Runtime 继承链 | `traced_runtime.InstrumentedAgentOpsRuntime` → `redis_runtime.RedisPostgresAgentOpsRuntime` → `postgres_runtime.PostgresAgentOpsRuntime` → `runtime.AgentOpsRuntime` | 合并为 Runtime 职责卡，保持单进程、单 Worker，未画成微服务 |
| Graph / State / LLM | `app/agent/workflow.py:AgentState/create_graph/tracked_chat_completion`；`app/agent/postgres_runtime.py:start` 创建 AsyncOpenAI | 图一 Workflow 与 SDK；图二将进程内 SDK 调用合并进 LangGraph lifeline，DeepSeek API 独立列为外部参与者 |
| Session 创建 | `postgres_runtime.create_session`；`app/storage/postgres_store.py` | 先提交 session_id → thread_id，再向 Client 返回；仅新会话 opt 分支 |
| 消息与现有状态 | `runtime.ask` 的锁、pending 检查、`aget_state/ainvoke`；`redis_runtime.enforce_message_rate_limit` | 图二展示 Redis quota 在 Trace scope 前；同一会话使用已有 thread |
| 事故规划与工具循环 | `workflow.planner_node/normalize_plan/collect_evidence_node`；`app/tools/observability_mcp_client.py:query_observability_tool` | Planner 生成 JSON 白名单计划；loop 表达计划内真实存在的工具遍历，不虚构原生 tool_calls 事故循环 |
| Observability MCP | `app/tools/observability_mcp_server.py`；Runtime `Client(StdioServerParameters(...))` | 独立本地 STDIO 子进程；返回合成 metrics/logs/traces/topology，非生产遥测 |
| Utility / RAG MCP | `app/tools/tool_config.py:SERVERS`、`mcp_tool_runtime.py`、`mcp_stdio_launcher.py`；`workflow.llm_node/mcp_tool_node` | 图一条件 chat 工具路径；图二选择 INC 诊断分支，未加入无调用关系的 RAG / Utility 参与者 |
| 本地 Retrieval 与外部 LLM | `app/rag/rag_pipeline.py:run_rag`；`retriever.py/reranker.py/answerability.py/generator.py` | 本地 Embedding、FAISS、Reranker 与外部判断/生成区分；无候选可提前返回，非所有 RAG 请求必调 LLM |
| 长期记忆 | `workflow.retrieve_memory_node`；`app/memory/memory_store.py/memory_retriever.py` | 历史提示，不作为当前事故证据；图二以内调用标注 |
| RCA 与有界再生成 | `workflow.rca_node`；`app/rca/rca_core.py` | 结构化 JSON → Python 校验；失败允许一次再生成，最终保守返回 |
| HITL | `workflow.prepare_proposal_node/human_approval_node`；`app/agent/hitl.py`；`runtime.approve` | 条件 interrupt，另一个 HTTP decision 请求通过 Command 在同一线程恢复；审批只产生模拟或拒绝审计 |
| PostgreSQL | `postgres_runtime.py` 的 AsyncPostgresSaver、SessionRepository、PostgresSimulationAudit；`app/storage/postgres_store.py` | Session、Checkpoint、Audit；Saver 在步骤和中断时保存，不只在 END，审计与 Saver 是分别写入 |
| Redis | `redis_runtime.py`；`app/storage/redis_store.py`；`docker-compose.yml` | 案例缓存与 Lua 原子消息限流；图二仅展示当前请求相关 quota，未虚构必经缓存读取 |
| Trace Collector | `app/telemetry/observability.py`、`trace_callback.py`；`traced_runtime.ask/_traced_call/_save_trace` | API 内存 Collector + 宿主机 JSONL；finally 记录后返回，不画成独立分布式平台 |
| 部署边界 | `scripts/manage.sh`、`docker-compose.yml`、`Dockerfile`、`docs/deployment.md` | Conda 宿主机 API/MCP；Compose 仅 PG/Redis，现有 Dockerfile 为 Redis 配置镜像 |
| 目录树 | 当前真实文件路径及 `app/` 九个职责包 | 图三包含 RCA、Storage、Telemetry；包含 architecture 图源文档；所有展示路径均真实存在，并随本次文档发布纳入 Git |

图二 HTTP 标签使用 `/sessions`、`/messages`、`/decisions` 的缩写；正式路由为 `POST /api/v1/sessions`、`POST /api/v1/sessions/{session_id}/messages`、`POST /api/v1/sessions/{session_id}/decisions`。图一支持总线表达 Runtime 持有的状态与观测适配器，不是每个请求都会执行的同步步骤，也不代表所有持久化写入处于同一事务。

## 导出交付与复现

| 交付 | SVG 逻辑尺寸 | 正式 PNG 尺寸 | 编辑源 |
|---|---|---|---|
| [系统分层图](figures/01-system-architecture.svg) | 1920 × 1080 | 3840 × 2160 | [draw.io](figures/01-system-architecture.drawio) |
| [请求时序图](figures/02-request-sequence.svg) | 2220 × 3607 | 4440 × 7214 | [draw.io](figures/02-request-sequence.drawio) |
| [项目目录图](figures/03-project-structure.svg) | 1700 × 1260 | 3400 × 2520 | [draw.io](figures/03-project-structure.drawio) |

[render_figures.py](figures/render_figures.py) 用同一几何定义导出原生 SVG、可编辑 mxGraph XML、FreeType 字体渲染的 2 倍 PNG。PNG 是正式光栅导出，无截图；SVG 保留文字和矢量图元。draw.io 包含独立图元与文字，卡片文字归属其父卡片，不是把整张图片塞入编辑文件。

当前环境没有 diagrams.net GUI，使用已有 NumPy、系统 FreeType 和 DejaVu 字体完成本地导出，没有安装依赖。XML 结构已检查；**没有执行 diagrams.net GUI 打开/另存的往返测试**。源文件与矢量 PNG 的跨工具字体排版可能有少量差异，应在编辑后重新导出。

在仓库根目录执行：

```bash
/home/ubuntu/miniconda3/envs/agent-dev/bin/python docs/architecture/figures/render_figures.py
```

该命令重新生成三图及 [export-manifest.json](figures/export-manifest.json)，不导入应用、不访问数据库或模型。复现环境需已有 NumPy、Linux FreeType 和 `/usr/share/fonts/truetype/dejavu/` 字体；自定义 ctypes FreeType 字段按当前 Linux 64 位环境实现，其他平台需适配或直接用 diagrams.net 编辑 `.drawio`。

## 实际视觉检查

已分别打开三张最终 PNG，而非仅检查绘图代码。

- 图一：检查 16:9 总体布局、四层对齐、标题/说明、外部 Provider 和图例；将 LLM Client 放在工具层右侧，使外部 API 连线直接横出，消除不必要的穿线。
- 图二：检查 Participant、生命线、请求/返回、自调用和条件框。发现并修复框标题被 Activation 盖住的问题；框背景在底层、标题在激活条上层。最终 PNG 已重新打开确认。长图适合点击 SVG 放大阅读，README 默认折叠，无法在窄屏缩略图中同时读清全部细节。
- 图三：检查树枝父子关系、目录突出、文件普通字重及职责列；白底留白，无虚构目录；architecture 图源与文档纳入本次发布；目录图已移除本地草稿标注。
- 三图无明显文字重叠或裁切；主业务线与状态辅助线样式分开。标题、注释和正文使用相同字体体系。

未执行参考原图的视觉比对，未执行 GitHub 远端页面渲染验证。

## README 变更与保留工作

[README](../../README.md) 的 Architecture 使用第一张 PNG 主图并链接 SVG / draw.io；Request Sequence 与 Project Structure 用 details 折叠呈现第二、第三张，保持 01 → 02 → 03 的顺序。所有图片使用仓库相对路径，并保留真实 E2E BLOCKED / 0 次调用说明。

发布范围包括 README、`docs/architecture.md`、`docs/architecture/` 的三图及审计文档，以及它们引用的既有 `docs/e2e/` 报告和 `verification/e2e/blocked-preflight.json`。配套报告在本轮开始前尚未提交，发布前已审阅并原样纳入，避免远程链接悬空。旧审查报告中的“未提交”等说明描述其对应验收阶段，不代表本次发布决定。未修改业务代码、测试、依赖、配置、数据库或数据卷；既有报告和证据以 SHA-256 核对保留。

## 验证边界与 Git 决策

真实执行：本地源码/路径审计、三格式导出、逐图 PNG 预览、XML/PNG/哈希/相对链接检查及 Git 差异检查。本次没有运行业务回归或模拟 Agent 流程，没有 DeepSeek API 调用、应用启动或基础设施变更。历史测试结果仍按原证据描述，不算本次测试。

未验证的运行关系：源码已实现的 DeepSeek 推理、真实模型驱动工具、完整 HITL 链路仍未获同一次真实端到端请求证明；最新 E2E 依旧 **BLOCKED（缺少 DEEPSEEK_API_KEY），真实调用 0 次**。图表达可执行代码定义的关系，不能代替真实集成验收。

用户已解除参考图比对的发布前提并明确授权推送。发布前 `git fetch origin` 成功，`main...origin/main` 左右计数为 `0 / 0`，双方基线均为 `4313fe1`，没有待处理远程提交或分叉。对审核过的文档及引用依赖创建独立文档提交，并使用普通 `git push origin main` 发布，不强制推送。此报告与新提交一同交付，提交自身哈希及实际推送回执由最终 Git 输出和 GitHub 提交页面记录，不在提交内容中预写自身哈希或假定尚未发生的远程结果。

## 本轮机器检查记录

以下为初次导出后的真实检查记录；发布前重新核对文档链接、图源哈希、路径、业务文件保护及暂存范围。

执行环境：Conda `agent-dev`；技术检查全部通过；当前发布标准由用户确认。

- PASS — 9 SVG / PNG / draw.io asset hashes match export-manifest.json
- PASS — 01-system-architecture: native vector SVG, editable XML (108 cells), PNG 3840x2160
- PASS — 02-request-sequence: native vector SVG, editable XML (218 cells), PNG 4440x7214
- PASS — 03-project-structure: native vector SVG, editable XML (133 cells), PNG 3400x2520
- PASS — Renderer Python syntax
- PASS — README.md: 32 relative links resolve
- PASS — docs/architecture/FIGURE_DESIGN_REVIEW.md: 11 relative links resolve
- PASS — README figure order and balanced collapsible sections
- PASS — 206 original code/config/test/document/evidence file hashes unchanged
- PASS — main / 4313fe1 unchanged; index empty; git diff --check passed

检查脚本首轮把“卡片文字分组”误设为全部图的要求，白底目录树无卡片而触发断言；已把此检查限定在两张有卡片的图，目录图仍检查每个图元及引用合法，复验通过。未因此更改图片。

当前验收结论：三图 PASS，源码一致性 PASS，高清 SVG/PNG PASS，README 更新 PASS。参考原图严格比对未执行且已获用户豁免。业务代码修改：否；提交及普通推送：用户已明确授权，执行回执见最终 Git 结果。
