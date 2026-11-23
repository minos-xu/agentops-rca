# Architecture Design Review

本次仅优化README、架构说明和可维护图源。源码基线为main / 4313fe1。**不改变业务能力、运行拓扑或验收结论。**

## 1. 原图与首页问题

- 旧总图将RAG、Utility、Observability并列直接连到Graph，没有清楚表示事故与普通问答的调用条件。
- 旧架构流程图只展示事故成功/审批路径，不能完整讲解一般问答循环、证据降级和早期拒绝。
- 主链、存储与Trace连线缺少视觉语义，读者容易把辅助能力当作连续推理阶段。
- DeepSeek虽位于图外，首页验证说明仍突出更早的学习历史，没有优先呈现最新BLOCKED状态。
- 目录片段把app/main.py写成app/app.main.py；部署边界、当前验证范围和技术亮点分散在多个位置。

## 2. 新设计

### Overview

15个组件节点、17条关系，使用LR横向布局，面向宽屏/16:9展示。API入口主链使用粗蓝线，Runtime/LangGraph紫色居中；MCP与检索为青绿，存储为橙色，外部Provider使用中性色。

Host包围API进程组件及MCP子进程；Docker组只包含PostgreSQL/Redis。DeepSeek保持在两者之外。RAG子进程中保留Local Retrieval模块边界，不引入额外服务。State在Graph节点内说明；HITL为条件中断/恢复，不是每次必须执行。

工具请求按分支表达：Observability用于INC证据；RAG/Utility为普通问答的条件调用。图注明确虚线的条件含义、Observe插桩含义、持久化细线及主消息请求范围，不将GET健康/查询画成完整Graph运行。

### Request Flow

30个节点、44条连线，独立放在技术文档中，避免把详细执行图堆到README首页。展示验证/Session/限流、Trace、pending保护、Graph分支、Planner受控计划、MCP取证、RCA校验/一次重生成/降级、普通问答工具循环与HITL另请求恢复。

细虚线表示步骤/中断的Checkpoint关系，不把持久化误写成仅结束时执行。Trace为旁路插桩；Checkpoint中断返回pending，不会先执行模拟动作。已知依赖异常、早期4xx/限流/Redis失败与无待审批冲突边界均说明。

这里只优先控制层级和连线语义，**没有本地渲染结果可证明最终像素布局或16:9比例**。详细流程图本身会比总图更高，应在GitHub中按需放大查看。

## 3. 源码审计

完整设计依据与A/B/C矩阵见 [SOURCE_AUDIT.md](SOURCE_AUDIT.md)。

- 正式入口app.main:app；api.routes.send_message先限流，再进入traced ask。
- Runtime继承链、Graph调用、Session/Checkpoint初始化、MCP module入口均按源码核对。
- 事故路径是LLM JSON规划 → Python白名单MCP取证 → 结构化RCA，不宣传为已经实测的ReAct循环。
- 普通问答支持原生tool_calls → ToolMessage → llm；仅rag_query才使用文档检索/重排/资料判断/生成。
- RAG/Utility并非每次请求必经，INC分支没有RAG调用边。长期Memory是历史启发，不能当作本次事故的观测证据。
- 审批执行只产生模拟审计；没有生产遥测连接、真实修复或恢复验证。
- Trace Collector为进程内对象，MCP内部事件不自动合并；没有画出未实现的分布式追踪后端。

## 4. 新旧主要差异

| 维度 | 原呈现 | 新呈现 |
|---|---|---|
| 主视角 | 模块连线集合 | 主请求 → 编排 → 分支工具，旁挂状态/观测 |
| 工具语义 | 所有工具看似平行必调 | INC证据与chat可选工具区分 |
| RAG | 缺少本地/外部计算区分 | 本地检索在RAG子进程，资料判断/生成连外部API |
| 进程边界 | 主机与容器边界较粗 | API进程组件、MCP子进程、Docker数据容器、外部Provider分别说明 |
| 执行说明 | 事故与审批简图 | 独立详细图，包含跳过/错误/降级/暂停/恢复 |
| 验证状态 | 历史说明不够突出 | 首页及图注明确最新真实DeepSeek E2E BLOCKED |

## 5. README 优化

1. 项目名称统一为AgentOps RCA；一句英文定位配简洁中文价值说明。
2. 首页直接放总架构，不要求先跳转其他页面；详细请求图移到技术说明。
3. 按Architecture、Core Features、Tech Stack、Project Structure、Quick Start、Validation、Documentation组织。
4. 修正main.py目录展示；增加目录职责入口，避免列举43个文件。
5. Quick Start沿用现有init/index/up --offline/health/test/stop，不发明配置或命令，不放真实Key。
6. 保留MIT与第三方许可，去掉可能混淆当前验收状态的历史DeepSeek宣传段落。
7. 页面明确0次真实调用、RAG/MCP独立验证、基础设施历史验收、真实LLM E2E未完成；不虚构徽章、性能指标或生产能力。

## 6. 文件清单与范围

修改：

- README.md
- docs/architecture.md

新增：

- docs/architecture/overview.mmd
- docs/architecture/request-flow.mmd
- docs/architecture/project-structure.md
- docs/architecture/SOURCE_AUDIT.md
- docs/architecture/ARCHITECTURE_DESIGN_REVIEW.md

图源与README/architecture.md的Mermaid代码块保持逐字一致。没有安装依赖、导出伪造SVG或引入draw.io重复版本；仓库也没有既有draw.io需要同步。

## 7. 检查结果

| 项目 | 结果 | 检查范围 |
|---|---|---|
| 图结构静态检查 | PASS | 节点ID、连线端点、subgraph配对、linkStyle索引 |
| 图源与Markdown副本 | PASS | README总图、architecture两图与.mmd逐字比较 |
| 本地文档链接与锚点 | PASS | 当前README、架构说明、目录与审计报告 |
| Quick Start入口 | PASS（静态） | 确认manage现有子命令与app.main:app；不启动服务 |
| 修改范围 | PASS | 允许范围之外200个文件SHA256保持不变，含既有未提交E2E报告 |
| Git空白检查 | PASS | git diff --check；新增文档另查尾空格与fence配对 |
| Mermaid CLI解析 | **NOT RUN** | 未安装mmdc/Node，未安装新依赖 |
| 实际SVG / 浏览器预览 | **NOT RUN** | 无本地Chromium/Chrome或Playwright/Selenium；未调用在线渲染服务 |
| GitHub页面实际渲染 | **待用户预览** | 未提交/推送，不能声称远程已成功渲染 |

静态结构检查不是完整Mermaid语法解析，更不等于字体、重叠、交叉线或像素可读性验证。采用基础flowchart/classDef语法降低兼容风险，但最终显示仍须在支持Mermaid的GitHub预览中确认。

本次是低影响文档变更，未重跑业务回归、数据库验收或模型探针；未把先前结果冒充本轮测试。没有API调用、数据库操作或模型调用。

## 8. 功能与验证状态

A为已实现；B为独立验证；C为同一真实LLM业务链路E2E。SOURCE_AUDIT中的来源分别注明离线Mock、实际本地计算、独立STDIO及历史真实基础设施。

当前A并不自动推导C。最近一次E2E因DEEPSEEK_API_KEY缺失为BLOCKED，真实API调用0次；没有真实LLM诊断结果，也没有生产准确率或负载结论。图所示关系是实现拓扑，不是已执行轨迹。

## 9. 业务与历史材料保护

未修改app/、tests/、scripts/、Schema、Prompt、模型/API配置、Compose、.env或其他项目。未修改或删除历史验证证据。此前docs/e2e/与verification/e2e/尚未提交的文件保持原样，本任务不代为暂存或提交它们。

没有Commit、Push、Merge或Release。修改保持供用户审核。

## 10. 后续建议与未解决事项

1. **视觉预览待确认**：GitHub渲染后检查长标签、缩放、组间间距和少量跨组连线；实际无预览前不能宣称“没有重叠”。如有需要，只调整图源和同步代码块，不改拓扑。
2. **发布引用完整性**：README引用的既有E2E报告当前在本地可达，但在本任务开始前尚未提交。后续发布时应把获准的既有报告一并审核纳入，避免远程链接悬空；本任务不越权提交。
3. **范围外既有文档笔误**：docs/deployment.md把生成索引写成app.rag.embedding_store.pkl / app.rag.bm25_store.pkl，实际是项目根embedding_store.pkl / bm25_store.pkl。该文件不在允许编辑范围，本次只记录；新目录说明采用实际路径。
4. **未来重新验收**：真实DeepSeek E2E补齐凭据和费用门禁后，再根据实际结果更新Validation；不要提前把pending改为passed。
5. **发布清单**：本次禁止修改根目录发布元数据；将来需要新ZIP时，再在获准范围更新RELEASE_FILES/SOURCE_MAPPING，确保新.mmd图源和文档被打包。

结论：图源、文档层级与源码语义审查已完成，未发现当前图示与已核对源码的实质关系冲突；实际Mermaid渲染/视觉验收仍待预览。不是“已通过真实LLM端到端”的宣传交付。
