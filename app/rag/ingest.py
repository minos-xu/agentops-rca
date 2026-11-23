import hashlib

from app.core.config import (
    DOCUMENT_DIR
)

from app.rag.loader import (
    load_documents
)

from app.rag.chunker import (
    split_by_paragraph,
    tokenize
)

from app.rag.embedder import (
    embed_texts
)

from app.rag.vector_store import (
    create_index,
    load_index,
    load_state,
    save_index,
    add_vectors,
    remove_vectors
)

from app.rag.embedding_store import (
    load_embedding_store,
    save_embedding_store
)

from app.rag.bm25_store import (
    build_bm25_store,
    save_bm25_store
)

def delete_document(
    document_id: str,
    index,
    state: dict,
    embedding_store: dict
):
    document = (
        state["documents"].get(
            document_id
        )
    )

    if not document:
        return

    vector_ids = (
        document["vector_ids"]
    )

    if index is not None:
        remove_vectors(
            index,
            vector_ids
        )

    for vector_id in vector_ids:

        state[
            "records"
        ].pop(
            str(vector_id),
            None
        )

        embedding_store.pop(
            vector_id,
            None
        )

    state[
        "documents"
    ].pop(
        document_id,
        None
    )

def calculate_hash(
    text: str
) -> str:

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def main():

    documents = load_documents(
        DOCUMENT_DIR
    )

    state = load_state()

    index = load_index()

    embedding_store = (
        load_embedding_store()
    )

    # ========================================
    # 1. 删除同步
    # ========================================

    current_document_ids = {
        document["document_id"]
        for document in documents
    }

    old_document_ids = set(
        state["documents"].keys()
    )

    deleted_document_ids = (
        old_document_ids
        - current_document_ids
    )


    for document_id in (
    deleted_document_ids
):

        print(
            f"删除文档："
            f"{document_id}"
        )

        delete_document(
            document_id,
            index,
            state,
            embedding_store
        )

    # ========================================
    # 2. 新增 / 更新 / 跳过
    # ========================================

    for document in documents:

        category = document["category"]
        document_id = document["document_id"]
        source = document["source"]
        text = document["text"]

        current_hash = calculate_hash(
            text
        )

        old_document = (
            state["documents"].get(
                document_id
            )
        )

        # ====================================
        # 1. 未发生变化
        # ====================================

        if (
            old_document
            and
            old_document["content_hash"]
            == current_hash
        ):

            print(
                f"跳过未变化文档：{document_id}"
            )

            continue

        # ====================================
        # 2. 先进行 Chunk
        # ====================================

        chunks = split_by_paragraph(
            text
        )


        # ====================================
        # 3. 先计算新的 embedding
        # ====================================

        if chunks:

            embeddings = embed_texts(
                chunks
            )

        # ====================================
        # 4. 删除旧版本
        # ====================================

        if old_document:

            print(
                f"更新文档：{document_id}"
            )

            delete_document(
                document_id,
                index,
                state,
                embedding_store
            )

        else:

            print(
                f"新增文档：{document_id}"
            )

        # ====================================
        # 5. 空文档
        # ====================================

        if not chunks:

            state[
                "documents"
            ][document_id] = {

                "content_hash":
                    current_hash,

                "vector_ids":
                    []
            }

            print(
                f"文档无有效 Chunk：{document_id}"
            )

            continue

        # ====================================
        # 6. 创建 Index
        # ====================================

        if index is None:

            dimension = (
                embeddings.shape[1]
            )

            index = create_index(
                dimension
            )

        # ====================================
        # 7. Vector IDs
        # ====================================

        vector_ids = []

        for _ in chunks:

            vector_id = (
                state["next_vector_id"]
            )

            state[
                "next_vector_id"
            ] += 1

            vector_ids.append(
                vector_id
            )

        # ====================================
        # 8. FAISS
        # ====================================

        add_vectors(
            index,
            embeddings,
            vector_ids
        )

        # ====================================
        # 9. Embedding Store
        # ====================================

        for (
            vector_id,
            embedding
        ) in zip(
            vector_ids,
            embeddings
        ):

            embedding_store[
                vector_id
            ] = embedding

        # ====================================
        # 10. Records
        # ====================================

        for (
            vector_id,
            chunk_index,
            chunk
        ) in zip(
            vector_ids,
            range(len(chunks)),
            chunks
        ):

            state[
                "records"
            ][str(vector_id)] = {

                "text": chunk,

                "metadata": {

                    "document_id":
                        document_id,

                    "source":
                        source,

                    "category":
                        category,

                    "chunk_index":
                        chunk_index
                }
            }

        # ====================================
        # 11. Document State
        # ====================================

        state[
            "documents"
        ][document_id] = {

            "content_hash":
                current_hash,

            "vector_ids":
                vector_ids
        }

    # ========================================
    # 3. 保存
    # ========================================

    if index is None:

        print(
            "当前没有任何可索引文档。"
        )

        return


    save_index(
        index,
        state
    )

    save_embedding_store(
        embedding_store
    )

    bm25_store = build_bm25_store(
    state["records"]
)

    save_bm25_store(
        bm25_store
    )

    print(
        "\n增量索引同步完成。"
    )


if __name__ == "__main__":
    main()