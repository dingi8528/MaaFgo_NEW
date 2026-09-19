# -*- coding: utf-8 -*-
"""羁绊补齐自动记忆的稳定键与本地持久化。"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone


SCHEMA_VERSION = 1
MAX_ENTRIES = 64


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_task_key(expected, settings) -> str:
    """按影响羁绊结果的稳定输入生成任务键，不使用一次性运行 ID。"""
    slots = []
    for item in expected:
        slots.append({
            "slot": int(item.get("slot", len(slots))),
            "kind": str(item.get("kind") or "EMPTY"),
            "svt_id": str(item.get("svt_id") or ""),
            "equip_id": str(item.get("equip_id") or ""),
            "equip_limit_break": bool(item.get("equip_limit_break", False)),
            "grand_svt": bool(item.get("grand_svt", False)),
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "slots": slots,
        "settings": settings,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def formation_signature(servants, equips):
    """生成可直接比较的六槽签名；调用方必须先排除未知状态。"""
    if len(servants) != 6 or len(equips) != 6:
        raise ValueError("编队签名必须包含六个槽位")
    normalized_servants = [str(value) for value in servants]
    normalized_equips = []
    for value in equips:
        if isinstance(value, list):
            normalized_equips.append([str(item) for item in value])
        else:
            normalized_equips.append(str(value))
    return {
        "servants": normalized_servants,
        "equips": normalized_equips,
    }


class BondCompletionMemory:
    def __init__(self, path):
        self.path = os.fspath(path)

    def _read(self):
        if not os.path.isfile(self.path):
            return {"schema_version": SCHEMA_VERSION, "entries": {}}
        with open(self.path, encoding="utf-8-sig") as stream:
            document = json.load(stream)
        if not isinstance(document, dict):
            raise ValueError("自动记忆顶层不是对象")
        if document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("自动记忆版本不兼容")
        entries = document.get("entries")
        if not isinstance(entries, dict):
            raise ValueError("自动记忆缺少 entries")
        for key, entry in entries.items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                raise ValueError("自动记忆条目格式无效")
            signature = entry.get("formation")
            if (
                not isinstance(signature, dict)
                or not isinstance(signature.get("servants"), list)
                or len(signature["servants"]) != 6
                or not isinstance(signature.get("equips"), list)
                or len(signature["equips"]) != 6
            ):
                raise ValueError("自动记忆编队签名无效")
        return document

    def get(self, task_key):
        entry = self._read()["entries"].get(str(task_key))
        return entry.get("formation") if entry is not None else None

    def put(self, task_key, signature):
        # 先经过统一校验和归一化，避免把部分识别结果写入缓存。
        signature = formation_signature(
            signature.get("servants", []), signature.get("equips", [])
        )
        document = self._read()
        entries = document["entries"]
        entries[str(task_key)] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "formation": signature,
        }
        if len(entries) > MAX_ENTRIES:
            ranked = sorted(
                entries.items(),
                key=lambda item: str(item[1].get("updated_at") or ""),
                reverse=True,
            )
            document["entries"] = dict(ranked[:MAX_ENTRIES])
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        temporary = f"{self.path}.{os.getpid()}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

