# AgentOps-RCA 公开发布最终审计

**READY AFTER MANUAL CONFIRMATION**

候选源码、必要文档、离线回归和真实本地基础设施验收通过。转为公开前，请完成原开发数据库密码轮换，核对 MIT 署名及可能的外部代码来源，并确认 GitHub 首批提交仅包含本次清单。目录可用于创建一个新的 Private 仓库。

## 审计结果

| 维度 | 结果 | 证据 |
|---|---|---|
| README | PASS | 首段交代故障调查、证据校验、合成场景和审批，技术面试官可从 [README](README.md) 顺着图追到工作流与部署。 |
| 目录结构 | PASS | 运行模块、评测、测试、部署、合成文档及脱敏验证均保留。历史课件和版本没有混入源码目录。 [文件归类](FILE_INVENTORY.md) |
| 重命名 | PASS | 75 条源文件映射两端存在，16 个核心定义的 AST 与原项目一致。核查了入口、动态执行、测试及部署引用；目录外实测 MCP。 [文件映射](SOURCE_MAPPING.json) |
| 敏感信息 | PASS | 全目录比对本机凭据并审查用途，未发现候选凭据或运行数据。原目录的旧开发密码风险仍存。 [安全审计](SECURITY_AND_PUBLICATION_CHECK.md) |
| 许可证 | REVIEW | 用户已确认发布权并选择 MIT，当前署名需所有者作最终确认。 [MIT](LICENSE) · [第三方声明](THIRD_PARTY_NOTICES.md) |
| 离线测试 | PASS | 12/12 组脚本以正式入口复跑。保留 10 组回归和评分、鲁棒性两组。 [结果](verification/final-audit.json) |
| 部署验证 | PASS | 本机独立 Compose、重建合成索引、真实 PostgreSQL / Redis / HTTP / MCP，Checkpoint 重启后读取一致。 [实测输出](verification/final-audit-runtime.txt) |
| Git 提交清单 | PASS | 发布候选没有 .git。用临时空 Git 仓库暂存，逐项对照允许清单并校验 ZIP。 [发布清单](RELEASE_MANIFEST.md) |

## README 与实际代码

- `main:app` → FastAPI 路由 → Trace Runtime → Redis 限流、PostgreSQL 会话映射和 LangGraph。事故遥测调用 Observability MCP；通用问题走 RAG 或 Utility 分支。图中将 PostgreSQL / Redis 标为状态与缓存设施，并显示 HITL 中断。 [系统架构](ARCHITECTURE.md) · [模块依赖](MODULE_DEPENDENCIES.json)
- PostgreSQL 保存 Session、Checkpoint 和模拟审计。LangGraph 在人工决策后恢复同一线程。模拟审计有幂等约束。评分组件供测试和评测使用。故障追踪保留元数据，处理动作写模拟回执。
- 招聘展示保留架构图、可直接执行的 HTTP 请求、Swagger 和审批路径。合成 Checkpoint 探针的成功输出有独立标签；截图、在线 RCA 结果和 Token 数可以用真实脱敏演示补充，本次没有添加虚构展示材料。

## 修复与验证

| 文件 | 原因与验证 |
|---|---|
| `README.md`、`DEPLOYMENT.md` | 对齐实际 MCP/HITL 拓扑、模型占用、离线能力、常见故障和停止操作；检查文档路径、参数及对应实测结果。 |
| `.gitignore` | 覆盖私钥、数据库及 sidecar、JSONL 和索引；临时 Git 验证样本被忽略，两份模板仍会纳入。 |
| `.env.example` | 将手动本地开发示例端口对齐发布 Compose 默认值；账号、密码和数据库名保留占位符。 |
| `requirements.txt` | 去掉未在部署手册给出、也未经本项目验证的 CPU-only 安装提示；依赖声明和锁定版本保持原值，运行 `pip check` 与已装依赖 dry run。 |
| 两份安全/发布报告、清单及 `verification/` 新证据 | 保留上一阶段报告并增加最终审计入口，补充本次扫描、回归与复现证据，复核每个新增文件的 Git 和 ZIP 归属。 |

本轮修改限于文档、保护规则、配置示例和验证材料。RCA、审批、数据库、恢复逻辑与测试断言均沿用候选版本。对原目录 337 个基线文件逐个核验哈希，无变更。 [文件清单与校验值](RELEASE_MANIFEST.md)

## 复现范围与限制

- 离线测试通过替身和故障注入覆盖 RCA、HITL、错误分类、有限重试、Trace 和恢复。正式运行器沿用现有临时 FaultSaver 标记适配，原测试文件与断言均保留。
- 真实探针创建 HTTP 会话，验证案例缓存 TTL、Lua 并发限流与 HTTP 429，再向真实 PostgreSQL Saver 写入合成消息。停止和重启后验证同一会话、同一 Checkpoint ID 和同一消息。测试卷保留，容器与宿主机 API 已停止。验收使用独立回环端口和新卷。
- 实测本地 FAISS 检索、重排、三个 MCP 服务发现、Utility 计算工具、Observability 合成日志及 RAG 的空知识库分支。公开目录自带合成文档，索引在本机生成。
- 本次使用已有 Linux 主机、已缓存的模型和基于 `agent-dev` 的依赖审计隔离环境。第二台全新机器安装与迁移、真实 DeepSeek RCA/RAG 生成、生产环境及完整镜像漏洞扫描未执行。OSV 公告结果仅覆盖查询时的 Python 锁定版本。
- 单 Worker、回环监听、无公网鉴权。运行状态和备份应保留在受控本机。 [部署与恢复手册](DEPLOYMENT.md)

## 公开前的所有者操作

1. 轮换历史脚本中仍匹配的原开发 PostgreSQL 密码。若历史资料曾分享，再按影响范围轮换其他对应的凭据并核查访问记录。候选中无相应密码，不应把原项目的配置或运行目录复制进仓库。
2. 核对 MIT 的最终署名。依赖、镜像与模型依各自许可，候选不附带其发行文件。若掌握工作区之外的第三方代码来源，发布前核实并补齐应有声明。
3. 可创建新的 **Private** 仓库 `agentops-rca`。完成上述确认并复核待发布提交之后再转 **Public**。 [逐项检查](GITHUB_PUBLICATION_CHECKLIST.md)

简历表述建议

> 实现基于 FastAPI、LangGraph 与 MCP 的证据驱动 RCA Agent，支持证据不足时拒绝给出结论、HITL 模拟审批与 PostgreSQL Checkpoint 恢复。通过 12 组离线回归，并使用独立 PostgreSQL、Redis 实例验证并发限流和会话重启持久化。
