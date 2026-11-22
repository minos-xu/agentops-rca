# 验证方式

## 12 组离线回归脚本

```bash
conda activate agent-dev
bash scripts/manage.sh test
```

测试从 `tests/` 和 `evaluation/` 加载，运行器复制源码、选择的测试及夹具到临时目录。它不复制本机凭据、运行数据或原知识库，通过测试配置与用例替身验证行为。Python TCP 连接保护及本地模型离线设置防止常规误连。运行结果写入 `test-results/offline/`，默认 Git 忽略。

原 10 组覆盖 HITL、图中断、RCA、PostgreSQL 适配、Redis 降级、回归门槛、Trace、插桩接线、异常分类和恢复。另外保留评分与鲁棒性两组。`tests/fixtures/trace_api.py` 是插桩接线测试夹具。恢复测试的原始 FaultSaver 在严格序列化下可能被浅复制，运行器继续沿用 Lesson 64 的临时共享故障标记适配，保留全部断言。`--original-tests` 可复查未经适配的行为。

## 使用真实基础设施验收

按部署手册选好全新 Compose 项目和端口。在仅限本地的部署目录中执行：

```bash
bash scripts/manage.sh up --offline
bash scripts/manage.sh health
bash scripts/manage.sh acceptance seed --state .deployment/probe.json
bash scripts/manage.sh stop
bash scripts/manage.sh up --offline
bash scripts/manage.sh acceptance verify --state .deployment/probe.json
bash scripts/manage.sh stop
```

`seed` 创建真实 HTTP 会话，验证 Redis 缓存与并发 Lua 限流，并通过实际 Saver 写入一条合成 Checkpoint。`verify` 对比重启后的会话、Checkpoint ID 和返回消息。该探针不调用 DeepSeek。验收自己创建的容器和卷，保留探针卷与数据。历史 DeepSeek 演示验证的是合成事故调查链路，生产遥测、生产权限和生产负载不在此验证范围内。

发布副本的复测结果见 [`verification/`](verification/) 和 [发布报告](GITHUB_PUBLICATION_REPORT.md)。
