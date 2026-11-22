from mcp.server import MCPServer

from rag_pipeline import (
    run_rag
)


mcp = MCPServer(
    "rag-server"
)


@mcp.tool()
def rag_query(question: str) -> dict:
    """
    查询内部知识库。

    当用户询问公司、产品、账号、密码、API、
    文件上传、退款、安全规则等内部信息时，
    应优先使用此工具查询。

    即使不确定知识库中是否存在答案，
    也可以调用此工具进行查询。
    如果知识库中没有相关资料，
    工具会返回 answerable=false。
    """

    return run_rag(question)


if __name__ == "__main__":

    mcp.run()