# DeepSeek API 环境与冒烟结果

结论：**BLOCKED**（前置凭据缺失，未发出模型请求）。不是API认证失败，也不是网络测试失败。

## 凭据与配置检查

| 来源 | 本轮结果 |
|---|---|
| 进程DEEPSEEK_API_KEY | 不存在 |
| 当前项目.env | 文件不存在 |
| 当前项目.env.docker | 存在，DEEPSEEK_API_KEY为空 |
| 显式AGENTOPS_ENV_FILE | 未设置；默认项目根.env不存在 |

未读取、复制其他项目凭据，未输出任何Key、DSN密码或代理值，未修改现有配置。配置缺失后立即禁止计费调用。

## 源码中的真实配置

- Agent：`app/agent/postgres_runtime.py:start`构造openai.AsyncOpenAI，base_url为 `https://api.deepseek.com`。
- Agent模型来自 `app/tools/tool_config.py:MODEL`：DEEPSEEK_MODEL，当前部署配置为 `deepseek-chat`。这是当前配置标识，不代表本轮验证了官方可用性。
- RAG：`app/core/config.py`构造同步OpenAI，正常地址 `https://api.deepseek.com/v1`；离线模式改为回环禁用地址。LLM_MODEL为 `deepseek-v4-flash`，answerability另有同名硬编码。它与Agent模型标识不同，兼容性尚需独立验证，未凭猜测改名。
- 本机SDK：openai 3.7.0；httpx 0.28.1；httpx2 2.12.0；MCP 2.1.1；LangGraph 1.2.16。
- HTTP_PROXY/HTTPS_PROXY/NO_PROXY环境变量存在，仅记录存在性，未输出代理值或改全局配置。
- Agent tracked_chat_completion设置SDK max_retries=0、LLM timeout=30s；有界调用层只对明确429重试，最多2次尝试；MCP10s、安全只读可有限重试。
- 结构化RCA max_tokens=2200，最多一次校验重生成。Planner和普通llm节点未设置统一输出Token上限。RAG同步Client没有接入Agent的tracked_chat_completion统一限额/用量汇总，SDK构造未显式收敛其默认重试。
- 一般问答配置tools/tool_choice=auto；INC事故Planner为JSON规划，不是原生tool_calls协议。

## 本轮真实请求记录

| 字段 | 结果 |
|---|---|
| LLM HTTP请求次数（含内部调用） | 0 |
| 最小真实冒烟 | 未执行：凭据门禁阻断 |
| 正式HTTP Agent E2E | 未执行 |
| DNS / TCP / TLS / DeepSeek HTTP连通性 | 未执行，不能判定正常或失败 |
| HTTP状态 / Request ID / 延迟 | 不适用，无请求 |
| Input / Output / Total Tokens | 0 / 0 / 0（无调用计数，不是API返回的Usage） |
| Usage是否返回 | 否，无请求 |
| 本轮调用产生的估算费用 | $0（没有计费调用；未查询账单） |

未拿极短聊天请求冒充Agent成功，未发无凭据请求来人为制造401。

## 恢复前的安全准备

在本服务器当前项目私有 `.env.docker` 或受控进程环境配置 **DEEPSEEK_API_KEY**；不要发送到聊天、提交Git或填写.env.example。优先用本机编辑器编辑已有文件，勿覆盖其他数据库配置。配置完成后可以由验收工具仅输出“存在/缺失”复核。

恢复调用前必须先核对DeepSeek官方当前模型与价格，再估算总输入/输出预算。本轮因未达到调用门禁，没有引用未经核对的实时单价，也不虚构后续调用费用。

必须先有覆盖同步/异步客户端、内部重试与MCP子进程的全局6次请求账本、累计Token/美元限制，再运行真实测试；不能只数顶层HTTP请求。可先限制为1次冒烟（极短提示，输出上限例如16），再仅选INC-001。无429时事故通常2次模型调用（Planner+RCA），RCA校验失败可再生成1次；若每个操作均出现一次429，事故分支最多6次API尝试，加冒烟会超6次，因此不能盲目执行默认最大重试并宣称预算受控。

这不是业务修复结论，而是后续验证工具必须提供的保护。本轮没有实现或运行无全局限额的自主循环，调用预算与$0.50目标均未消耗。
