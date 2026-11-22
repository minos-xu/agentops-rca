from __future__ import annotations

import json

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path
from uuid import uuid4

import re
from datetime import datetime, timezone
from uuid import uuid4

class MemoryStore:

    def __init__(
        self,
        file_path: str | Path,
    ):

        self.file_path = Path(
            file_path
        )

        # 保证目录存在
        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.data = self._load()

    # =========================================
    # Load
    # =========================================

    def _load(
        self,
    ) -> dict:

        if not self.file_path.exists():

            return {
                "memories": []
            }

        try:

            with self.file_path.open(
                "r",
                encoding="utf-8",
            ) as f:

                return json.load(f)

        except (
            json.JSONDecodeError,
            OSError,
        ) as e:

            raise RuntimeError(
                "读取 Memory 文件失败："
                f"{e}"
            ) from e

    # =========================================
    # Save
    # =========================================

    def _save(
        self,
    ):

        with self.file_path.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                self.data,
                f,
                ensure_ascii=False,
                indent=2,
            )

    # =========================================
    # Add Memory
    # =========================================

    def add(
        self,
        text: str,
    ) -> dict | None:

        text = text.strip()

        if not text:
            return None

        # -------------------------------------
        # 简单去重
        # -------------------------------------

        for memory in self.data[
            "memories"
        ]:

            if memory["text"] == text:

                return memory

        # -------------------------------------
        # 新建 Memory
        # -------------------------------------

        memory = {
            "id": str(
                uuid4()
            ),

            "text": text,

            "created_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }

        self.data[
            "memories"
        ].append(
            memory
        )

        self._save()

        return memory

    # =========================================
    # Get All
    # =========================================

    def get_all(
        self,
    ) -> list[dict]:

        return list(
            self.data[
                "memories"
            ]
        )

    # =========================================
    # Clear
    # =========================================

    def clear(
        self,
    ):

        self.data = {
            "memories": []
        }

        self._save()


    # =========================================
    # Get Memory By Key
    # =========================================

    def get_by_key(self, key: str) -> dict | None:

        key = key.strip()
        legacy_prefix = f"【{key}】"

        matches = []

        for memory in self.data["memories"]:

            # 新格式：独立 key 字段
            if memory.get("key") == key:
                matches.append(memory)

            # 兼容 Lesson 42 的旧前缀格式
            elif (
                not memory.get("key")
                and memory["text"].startswith(legacy_prefix)
            ):
                matches.append(memory)

        if len(matches) > 1:
            raise ValueError(
                f"发现重复 Memory key: {key}"
            )

        return dict(matches[0]) if matches else None

    # =========================================
    # Upsert: Add / Update / Unchanged
    # =========================================

    def upsert(
        self,
        key: str,
        text: str,
    ) -> dict:

        key = key.strip()
        text = text.strip()

        if not re.fullmatch(
            r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+",
            key,
        ):
            raise ValueError(
                f"Memory key 格式不正确: {key}"
            )

        if not text:
            raise ValueError("Memory text 不能为空")

        existing = self.get_by_key(key)

        now = datetime.now(
            timezone.utc
        ).isoformat()

        # -------------------------------------
        # ADD
        # -------------------------------------

        if existing is None:

            memory = {
                "id": str(uuid4()),
                "key": key,
                "text": text,
                "created_at": now,
                "updated_at": now,
            }

            self.data["memories"].append(memory)
            self._save()

            return {
                "status": "added",
                "memory": dict(memory),
                "old_text": None,
            }

        # -------------------------------------
        # 兼容旧格式
        # -------------------------------------

        old_text = existing["text"]
        legacy_prefix = f"【{key}】"

        if old_text.startswith(legacy_prefix):
            old_text = old_text[len(legacy_prefix):]

        # -------------------------------------
        # UNCHANGED
        # -------------------------------------

        if (
            old_text == text
            and existing.get("key") == key
        ):
            return {
                "status": "unchanged",
                "memory": existing,
                "old_text": old_text,
            }

        # -------------------------------------
        # UPDATE
        # -------------------------------------

        for memory in self.data["memories"]:

            if memory["id"] == existing["id"]:

                memory["key"] = key
                memory["text"] = text
                memory["updated_at"] = now

                self._save()

                status = (
                    "updated"
                    if old_text != text
                    else "normalized"
                )

                return {
                    "status": status,
                    "memory": dict(memory),
                    "old_text": old_text,
                }

        raise RuntimeError(
            "Memory 记录在更新时丢失"
        )

    def bind_legacy_key(
        self,
        memory_id: str,
        key: str,
    ) -> dict:

        key = key.strip()

        if not re.fullmatch(
            r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+",
            key,
        ):
            raise ValueError("非法 Memory key")

        existing = self.get_by_key(key)

        if (
            existing is not None
            and existing["id"] != memory_id
        ):
            raise ValueError(
                f"Key {key} 已绑定其他 Memory"
            )

        for memory in self.data["memories"]:

            if memory["id"] == memory_id:

                old_key = memory.get("key")

                if old_key and old_key != key:
                    raise ValueError(
                        "不能直接改写已有 Memory key"
                    )

                memory["key"] = key

                memory["updated_at"] = (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                )

                self._save()

                return dict(memory)

        raise ValueError(
            f"找不到 Memory ID: {memory_id}"
        )
