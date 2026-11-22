# Linux 部署手册

## 环境和模型

准备 Linux、Docker Engine、Docker Compose 和 Conda。历史和本次验证使用 x86_64 与 Python 3.12.14。依赖约束记录于 `requirements.lock.txt`。一次全新的跨机器安装涉及平台匹配的 Python wheel、Compose 镜像和模型下载。

```bash
conda env create -f environment.yml
conda activate agent-dev
python -m pip check
```

`manage.sh` 使用当前 `CONDA_PREFIX/bin/python`，也可通过 `AGENTOPS_PYTHON` 指定 `agent-dev` 的解释器。API 和 MCP 均沿用该解释器。

两套权重独立准备。已有本地模型可直接使用，网络可用且有权获取模型时可以运行：

```bash
python - <<'PY'
from pathlib import Path
import json
from huggingface_hub import snapshot_download

manifest = json.loads(Path('deploy/models.manifest.json').read_text())
base = Path.home() / 'models'
for model in manifest.values():
    snapshot_download(model['repository'], revision=model['revision'],
                      local_dir=str(base / model['repository'].split('/')[-1]))
PY
python scripts/verify_models.py \
  --embedding "$HOME/models/bge-small-zh-v1.5" \
  --reranker "$HOME/models/bge-reranker-v2-m3"
```

模型清单中需校验的文件合计约 2.4 GB。上述命令下载整个固定快照，请额外预留其他上游文件、Python 依赖和容器镜像的空间。模型许可随上游模型，见 [第三方说明](THIRD_PARTY_NOTICES.md)。

## 初始化、建立索引和启动

```bash
bash scripts/manage.sh init
# 编辑 .env.docker，设置 EMBEDDING_MODEL_PATH 和 RERANKER_MODEL_PATH
bash scripts/manage.sh index
bash scripts/manage.sh compose config --quiet
bash scripts/manage.sh up --offline
bash scripts/manage.sh health
bash scripts/manage.sh status
```

`init` 根据 `.env.docker.example` 生成本地配置与随机 PostgreSQL 密码，保留已有配置。`index` 使用本地 Embedding 把 `documents/demo_ops_manual.txt` 编入 FAISS，并生成 `metadata.json`、`embedding_store.pkl` 和 `bm25_store.pkl`。该步骤使用离线配置，不需要模型服务密钥。保持 API 停止再重建索引，只使用信任的文档与本机生成的索引。

默认 Compose 项目名 `agentops-rca`，API、PostgreSQL 和 Redis 分别使用回环端口 `8164`、`57432`、`57479`。另建实例时指定独立项目名、端口和数据目录。Compose 启动两个容器，宿主机运行单 Worker FastAPI 和它的 MCP STDIO 子进程。完整健康检查包含 PostgreSQL `SELECT 1`、Redis `PING`、API `/health`。

离线启动使用测试占位 Key，宿主 API 拦截所使用的 HTTPX/HTTPX2 非回环请求，RAG 模型请求目标为回环禁用端口。初次构建镜像仍可能访问镜像仓库。在线演示需在私有 `.env.docker` 中配置有效 `DEEPSEEK_API_KEY`，然后先 `stop` 再执行 `up`。查看 `/docs` 或使用本地 SSH 端口转发访问，服务保持回环绑定。

```bash
bash scripts/manage.sh logs api
bash scripts/manage.sh stop
```

## 常见启动问题

| 现象 | 检查方法 |
|---|---|
| 模型找不到或哈希校验失败 | 检查 `.env.docker` 的两个模型目录，再运行 `scripts/verify_models.py`。 |
| 索引文件缺失 | 停止 API，确认使用公开合成文档，然后重跑 `bash scripts/manage.sh index`。 |
| 端口冲突或 Compose 服务不健康 | 检查 `.env.docker` 中的回环端口是否被占用，查看 `bash scripts/manage.sh logs`。新实例使用独立项目名与数据目录。 |
| API 未启动 | 运行 `python -m pip check`，再用 `bash scripts/manage.sh logs api` 查看错误。 |

## 保存数据与恢复

`stop` 停止受管进程和容器，保留 PostgreSQL 命名卷及宿主机数据。Redis 的缓存和计数可重建。`bash scripts/manage.sh backup` 在 API 停止写入期间生成 `postgres.dump`、`files.tar.gz` 与 `SHA256SUMS`，随后以原模式恢复 API。备份包含会话、Checkpoint、审计、Memory、Trace 和 RAG 文件，应在受控位置保存。运行 `sha256sum -c SHA256SUMS` 验证文件。

恢复演练使用独立 `.env.docker`、新的 Compose 项目名、未占用的端口和新空数据库卷。先配置新环境，使用 `bash scripts/manage.sh compose config --quiet` 准备本地 secret，然后只启动 PostgreSQL，并将备份导入新空数据库。以下命令假定目标实例叫 `agentops-rca-restore`，数据库名与用户都使用模板默认值。

```bash
docker compose --project-name agentops-rca-restore --env-file .env.docker \
  -f docker-compose.yml up -d --wait postgres
docker compose --project-name agentops-rca-restore --env-file .env.docker \
  -f docker-compose.yml exec -T postgres \
  pg_restore --username agentops --dbname agentops --no-owner --no-privileges \
  < /path/to/private/backup/postgres.dump
```

API 停止时按备份内容恢复部署 `data/` 和 `knowledge/` 下的对应文件。启动后通过 `health` 和 [验收步骤](TESTING.md) 检查会话、Checkpoint 和审计。查看服务状态用 `bash scripts/manage.sh status`，容器日志用 `bash scripts/manage.sh logs`，API 日志用 `bash scripts/manage.sh logs api`。
