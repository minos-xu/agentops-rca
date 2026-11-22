# 第三方组件与授权来源

候选目录保留项目代码和基于合成数据的测试。目录中未发现注明从上游复制的第三方源文件、独立的第三方版权头或 vendored 包。发布包不分发已安装依赖、Docker 镜像或模型权重。无法从当前工作区的文件推定项目代码的权属或历史来源，用户已确认对公开内容的授权权利并选择 MIT。项目许可证见 [LICENSE](LICENSE)。

下表是本机已安装直接依赖的许可证元数据，供确认来源时使用。依赖各自的完整许可与版权声明以上游发行包为准。

| 组件 | 已安装发行包所声明的许可证 |
|---|---|
| FastAPI、LangGraph、LangChain Core、MCP、FAISS、redis-py、jieba、Pydantic | MIT |
| Uvicorn、HTTPX、python-dotenv | BSD-3-Clause |
| Sentence Transformers、OpenAI SDK、rank-bm25 | Apache-2.0（发行包元数据） |
| psycopg | LGPL-3.0-only |
| NumPy、PyTorch | 多许可证，见各发行包元数据和随附声明 |

PostgreSQL 与 Redis 使用 Compose / Dockerfile 指定的上游镜像。Redis 派生镜像在使用者本机构建，镜像分发的权利与义务以所选上游版本为准。BAAI Embedding 与 Reranker 的模型来源、实际版本及文件校验值见 `deploy/models.manifest.json`。获取或再分发模型前核对对应 revision 的上游模型卡和许可文本。

本次核对的固定 revision 模型卡声明：Embedding `bge-small-zh-v1.5` 为 MIT，Reranker `bge-reranker-v2-m3` 为 Apache-2.0。候选仅保留模型名、revision 与哈希。
