
from __future__ import annotations

import hashlib
import json
import os

from pathlib import Path

import faiss
import numpy as np

from embedder import embed_texts
from memory_store import MemoryStore


class SemanticMemoryRetriever:

    def __init__(
        self,
        memory_store: MemoryStore,
        top_k: int = 3,
        min_score: float = 0.5,
        model_key: str = "BAAI/bge-small-zh-v1.5",
    ):

        if top_k < 1:
            raise ValueError("top_k 必须大于 0")

        self.memory_store = memory_store
        self.top_k = top_k
        self.min_score = min_score

        # 应与 embed_texts() 实际使用的模型一致
        self.model_key = model_key

        data_dir = memory_store.file_path.parent

        self.index_path = (
            data_dir / "memory_vectors.faiss"
        )

        self.state_path = (
            data_dir / "memory_vectors_state.json"
        )

        self.index = None
        self.state = self._new_state()

        # 加载已有向量索引
        self._load()

        # 启动时检查新增、修改、删除
        self.sync()

    # ==========================================
    # State
    # ==========================================

    def _new_state(self) -> dict:

        return {
            "model_key": self.model_key,
            "next_vector_id": 1,
            "records": {},
        }

    def _hash_text(self, text: str) -> str:

        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    # ==========================================
    # Load Index
    # ==========================================

    def _load(self):

        if not (
            self.index_path.exists()
            and self.state_path.exists()
        ):
            return

        with self.state_path.open(
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

        index = faiss.read_index(
            str(self.index_path)
        )

        # Embedding 模型改变时需要重建
        if state.get("model_key") != self.model_key:

            print(
                "[Memory Index] 模型发生变化，"
                "准备重建索引"
            )

            return

        records = state["records"]

        expected_ids = {
            int(record["vector_id"])
            for record in records.values()
        }

        actual_ids = set(
            faiss.vector_to_array(
                index.id_map
            ).tolist()
        )

        # 防止 Index 与 State 不一致
        if expected_ids != actual_ids:

            print(
                "[Memory Index] Index/State "
                "不一致，准备重建"
            )

            return

        self.index = index
        self.state = state

        print(
            "[Memory Index] loaded, "
            f"vectors={index.ntotal}"
        )

    # ==========================================
    # Save Index + State
    # ==========================================

    def _save(self):

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 先保存 FAISS 索引
        if self.index is not None:

            temp_index = self.index_path.with_name(
                self.index_path.name + ".tmp"
            )

            faiss.write_index(
                self.index,
                str(temp_index),
            )

            os.replace(
                temp_index,
                self.index_path,
            )

        elif self.index_path.exists():

            self.index_path.unlink()

        # 再保存 State
        temp_state = self.state_path.with_name(
            self.state_path.name + ".tmp"
        )

        with temp_state.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                self.state,
                f,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temp_state,
            self.state_path,
        )

    # ==========================================
    # Sync Memory → FAISS
    # ==========================================

    def sync(self):

        memories = self.memory_store.get_all()

        memory_map = {
            memory["id"]: memory
            for memory in memories
        }

        records = self.state["records"]

        remove_ids = []
        pending = []

        # --------------------------
        # 1. 检测删除 / 修改
        # --------------------------

        for memory_id, record in list(
            records.items()
        ):

            memory = memory_map.get(
                memory_id
            )

            if memory is None:

                remove_ids.append(
                    record["vector_id"]
                )

                del records[memory_id]

                continue

            current_hash = self._hash_text(
                memory["text"]
            )

            if current_hash != record["text_hash"]:

                remove_ids.append(
                    record["vector_id"]
                )

                del records[memory_id]

        # --------------------------
        # 2. 从 FAISS 删除旧向量
        # --------------------------

        if remove_ids and self.index is not None:

            ids = np.asarray(
                remove_ids,
                dtype=np.int64,
            )

            self.index.remove_ids(ids)

        # --------------------------
        # 3. 找新增 / 修改的 Memory
        # --------------------------

        for memory in memories:

            if memory["id"] not in records:

                pending.append(memory)

        # --------------------------
        # 4. 只 Embedding 变化的 Memory
        # --------------------------

        if pending:

            texts = [
                memory["text"]
                for memory in pending
            ]

            vectors = np.asarray(
                embed_texts(texts),
                dtype=np.float32,
            )

            if vectors.ndim != 2:
                raise ValueError(
                    "Embedding 必须是二维数组"
                )

            faiss.normalize_L2(vectors)

            dimension = vectors.shape[1]

            if self.index is None:

                self.index = faiss.IndexIDMap2(
                    faiss.IndexFlatIP(
                        dimension
                    )
                )

            if self.index.d != dimension:
                raise ValueError(
                    "Embedding 维度与现有索引不一致，"
                    "请检查 model_key"
                )

            start_id = self.state[
                "next_vector_id"
            ]

            vector_ids = np.arange(
                start_id,
                start_id + len(pending),
                dtype=np.int64,
            )

            self.index.add_with_ids(
                vectors,
                vector_ids,
            )

            for memory, vector_id in zip(
                pending,
                vector_ids,
            ):

                records[memory["id"]] = {
                    "vector_id": int(vector_id),
                    "text_hash": self._hash_text(
                        memory["text"]
                    ),
                }

            self.state["next_vector_id"] += (
                len(pending)
            )

        # --------------------------
        # 5. 持久化变化
        # --------------------------

        if pending or remove_ids or not self.state_path.exists():

            self._save()

            print(
                "[Memory Index] sync "
                f"embedded={len(pending)}, "
                f"removed={len(remove_ids)}"
            )

        else:

            print(
                "[Memory Index] cache hit, "
                "no embedding needed"
            )

    # ==========================================
    # Retrieve
    # ==========================================

    def retrieve(
        self,
        query: str,
    ) -> list[dict]:

        # 只同步变化，不重新计算全部向量
        self.sync()

        if self.index is None:
            return []

        if self.index.ntotal == 0:
            return []

        # --------------------------
        # Query Embedding
        # --------------------------

        query_vector = np.asarray(
            embed_texts([query]),
            dtype=np.float32,
        )

        faiss.normalize_L2(
            query_vector
        )

        if query_vector.shape[1] != self.index.d:
            raise ValueError(
                "Query Embedding 维度不匹配"
            )

        # --------------------------
        # FAISS Search
        # --------------------------

        k = min(
            self.top_k,
            self.index.ntotal,
        )

        scores, vector_ids = (
            self.index.search(
                query_vector,
                k,
            )
        )

        # --------------------------
        # Vector ID → Memory ID
        # --------------------------

        vector_to_memory = {
            record["vector_id"]: memory_id
            for memory_id, record
            in self.state["records"].items()
        }

        memory_map = {
            memory["id"]: memory
            for memory
            in self.memory_store.get_all()
        }

        results = []

        for score, vector_id in zip(
            scores[0],
            vector_ids[0],
        ):

            score = float(score)
            vector_id = int(vector_id)

            if score < self.min_score:
                continue

            memory_id = vector_to_memory.get(
                vector_id
            )

            if memory_id is None:
                continue

            memory = memory_map.get(
                memory_id
            )

            if memory is None:
                continue

            results.append(
                {
                    **memory,
                    "score": score,
                }
            )

        return results
