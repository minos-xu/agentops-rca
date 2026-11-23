# 完整回归结果

验收日期：2026-11-23。所有项目Python/MCP均使用Conda agent-dev / Python3.12.14。

## 12组离线基线对照

| 脚本 | 重构前 | 重构后 | 后耗时(s) | 日志 |
|---|---|---|---|---|
| test_hitl.py | PASS | PASS | 0.065 | [日志](../../verification/refactor/after/test_hitl.txt) |
| test_workflow_interrupt.py | PASS | PASS | 1.017 | [日志](../../verification/refactor/after/test_workflow_interrupt.txt) |
| test_rca.py | PASS | PASS | 0.065 | [日志](../../verification/refactor/after/test_rca.txt) |
| test_postgres_store.py | PASS | PASS | 0.115 | [日志](../../verification/refactor/after/test_postgres_store.txt) |
| test_redis_degradation.py | PASS | PASS | 0.215 | [日志](../../verification/refactor/after/test_redis_degradation.txt) |
| test_eval_regression.py | PASS | PASS | 0.064 | [日志](../../verification/refactor/after/test_eval_regression.txt) |
| test_eval_scoring.py | PASS | PASS | 0.064 | [日志](../../verification/refactor/after/test_eval_scoring.txt) |
| test_eval_robustness.py | PASS | PASS | 0.065 | [日志](../../verification/refactor/after/test_eval_robustness.txt) |
| test_observability.py | PASS | PASS | 10.641 | [日志](../../verification/refactor/after/test_observability.txt) |
| test_trace_wiring.py | PASS | PASS | 0.064 | [日志](../../verification/refactor/after/test_trace_wiring.txt) |
| test_error_classification.py | PASS | PASS | 0.916 | [日志](../../verification/refactor/after/test_error_classification.txt) |
| test_recovery.py | PASS | PASS | 11.298 | [日志](../../verification/refactor/after/test_recovery.txt) |

完整证据位于项目根 `verification/refactor/`：before 为原12组基线，after 为正式 `bash scripts/manage.sh test` 的最终结果；所有测试断言、strict msgpack、网络连接禁止和既有FaultSaver共享开关临时兼容适配均保留。不把脚本组数混同测试用例数。

## 真实运行与模拟边界

| 检查 | 实际执行 | 证据（verification/refactor/） |
|---|---|---|
| 本地RAG | 公开合成文档读取、真实Embedding、FAISS检索、真实Reranker；没有LLM生成 | index.txt / rag.txt |
| 空证据 | 只Mock候选检索为空，断言保守返回 | rag.txt |
| MCP | 从/tmp运行探针；三类STDIO真实发现、Utility计算、四类Observability合成遥测调用、安全退出 | mcp.txt |
| 模块导入 | 所有app模块真实导入，未发生循环导入 | imports.txt |
| Compose/API | 实际构建Redis镜像、健康依赖、跨目录up/status/health/stop | infra-*.txt |
| PostgreSQL/HTTP | 真实Session创建、Saver写入合成消息、HTTP读取 | infra-seed.txt |
| Redis | 真缓存/TTL、Lua并发、HTTP429及Retry-After | infra-seed.txt |
| Checkpoint | API与两个容器停止/启动后，相同ID和内容恢复 | infra-verify.txt |
| HITL | 12组回归的离线中断/恢复；真实HTTP无待审批拒绝409 | after/ / trace.json |
| Trace | 真实HTTP拒绝请求写JSONL，关联会话、零LLM调用 | trace.json |
| 备份 | 实际pg_dump与文件备份，自动恢复API，再次读取Checkpoint | infra-backup.txt / infra-verify-backup.txt |
| 恢复 | 新空PostgreSQL卷真实pg_restore，Session/Checkpoint/消息一致；停止后保留卷 | restore.json |
| 安全 | 原学习项目文件校验、许可证/依赖/Compose不变、stderr脱敏、stdout协议不变 | safety.json |
| 业务对照 | 关键规则/存储类、create_graph AST、提示词和原assert不变 | semantic-parity.json |

部署测试只使用新项目 `agentops-rca-layout-20261123`、端口58432/58479/8264与独立卷；恢复测试另建 `agentops-rca-layout-restore-*`。原AgentOps、Lesson64以及AI Document Processing Platform的数据库没有连接、修改或清理。新验证容器最后只停止，卷保留。

真实DeepSeek生成、生产遥测、生产动作、负载与第二台干净服务器安装未执行。模型加载和合成数据实验不代表生产准确率。

## 发现与处理

首次迁移回归11/12通过：Trace语法检查仍指向旧文件位置，已修复路径；原失败完整保存在initial-migration。精确AST导入改写替代了初版过宽的字符串替换，避免修改业务标签/提示词。

真实Trace探针最初误以为摘要顶层含session_id；根据原格式summary.events修正探针断言，未改应用。部分离线API启动日志出现HuggingFace可选配置元数据HEAD重试，被原有HTTPX离线保护拦截；没有调用DeepSeek，启动最终成功。此为已有模型/SDK配置行为，本次没有顺手改写。

打包结果、文件允许清单、解压迁移及安全扫描证据见 package.json（最终打包后生成）。历史verification材料保持不变。
