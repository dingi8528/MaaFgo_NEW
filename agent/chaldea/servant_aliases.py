# -*- coding: utf-8 -*-
"""将 Chaldea 的同一从者多形态 ID 归一到 MaaFGO 的规范从者记录。"""


def servant_aliases(servant):
    """返回从者记录声明的形态别名 ID，排除自身 ID。"""
    canonical = str(servant.get("id") or "")
    return {
        str(alias)
        for alias in servant.get("aliases") or []
        if str(alias) and str(alias) != canonical
    }


def build_servant_lookup(servants):
    """构建 ID -> 规范从者记录映射；显式 aliases 优先于旧的重复记录。"""
    items = list(servants or [])
    lookup = {}
    for servant in items:
        sid = str(servant.get("id") or "")
        if not sid:
            continue
        if sid in lookup:
            raise ValueError(f"duplicate servant id: {sid}")
        lookup[sid] = servant

    alias_owners = {}
    for servant in items:
        canonical = str(servant.get("id") or "")
        for alias in servant_aliases(servant):
            owner = alias_owners.get(alias)
            if owner is not None and owner != canonical:
                raise ValueError(
                    f"servant alias {alias} belongs to both {owner} and {canonical}"
                )
            alias_owners[alias] = canonical

    # 覆盖可能残留在旧目录中的“形态 ID 独立记录”。例如 1002100 过去曾被
    # 错当成另一名从者；规范记录 1002000 声明 aliases 后应始终取得芙萝拉。
    for alias, canonical in alias_owners.items():
        servant = lookup.get(canonical)
        if servant is None:
            raise ValueError(f"servant alias {alias} references missing {canonical}")
        lookup[alias] = servant
    return lookup


def canonical_servants(servants):
    """过滤被 aliases 吸收的旧重复记录，只保留规范身份。"""
    items = list(servants or [])
    lookup = build_servant_lookup(items)
    return [
        servant
        for servant in items
        if lookup.get(str(servant.get("id") or "")) is servant
    ]
