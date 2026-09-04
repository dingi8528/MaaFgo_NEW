# -*- coding: utf-8 -*-
"""羁绊补齐的纯计算逻辑。

本模块不依赖 MaaFramework，也不访问网络，便于对匹配规则和组合规划做单元测试。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


SEVEN_CLASSES = {
    "saber_class",
    "archer_class",
    "lancer_class",
    "rider_class",
    "caster_class",
    "assassin_class",
    "berserker_class",
}


@dataclass(frozen=True)
class EquipPlan:
    equips: tuple[dict, ...]
    cost: int
    score: int


def rarity_order(preferred: int) -> list[int]:
    """返回用户优先星级加 5→0 的稳定去重顺序。"""
    preferred = int(preferred)
    if preferred < 0 or preferred > 5:
        raise ValueError("preferred rarity must be between 0 and 5")
    return list(dict.fromkeys([preferred, 5, 4, 3, 2, 1, 0]))


def servant_trait_variants(servant: Mapping) -> tuple[frozenset[str], ...]:
    """将基础、灵基与灵衣标签展开成可评分的状态集合。

    列表图片无法可靠区分所有灵基状态时，调用者可使用这些状态中的最高收益值；
    若已识别具体状态，则可直接把对应标签作为 ``bond.tags`` 传入。
    """
    bond = servant.get("bond") or {}
    base = {str(tag) for tag in (bond.get("tags") or []) if tag}
    result = {frozenset(base)}
    ascension = bond.get("tags_by_ascension") or {}
    values = ascension.values() if isinstance(ascension, Mapping) else []
    for tags in values:
        result.add(frozenset(base | {str(tag) for tag in (tags or []) if tag}))
    costume = bond.get("tags_by_costume") or {}
    if isinstance(costume, Mapping):
        costume_values = costume.values()
    elif isinstance(costume, Sequence) and not isinstance(costume, (str, bytes)):
        costume_values = [costume]
    else:
        costume_values = []
    for tags in costume_values:
        result.add(frozenset(base | {str(tag) for tag in (tags or []) if tag}))
    return tuple(sorted(result, key=lambda item: (len(item), tuple(sorted(item)))))


def target_matches(target: str, traits: Iterable[str]) -> bool:
    """复刻参考 HTML 的礼装目标匹配规则。"""
    trait_set = set(traits)
    if target == "all":
        return True
    if target == "lawful_good":
        return "lawful" in trait_set and "good" in trait_set
    if target == "lawful_female":
        return "lawful" in trait_set and "female" in trait_set
    if target == "chaotic_seven":
        return "chaotic" in trait_set and bool(SEVEN_CLASSES & trait_set)
    if target == "star_or_evil":
        return "star_power" in trait_set or "evil" in trait_set
    if target == "beast":
        return "beast_class" in trait_set
    return target in trait_set


def equip_is_permanent_bond(equip: Mapping) -> bool:
    bond = equip.get("bond") or {}
    if bond.get("bonus_type") not in {"percent", "flat_per_servant"}:
        return False
    # 带活动条件的效果已归档，但默认不用于常驻羁绊补齐。
    if bond.get("event_id"):
        return False
    for effect in bond.get("atlas_effects") or []:
        if isinstance(effect, Mapping) and effect.get("event_id"):
            return False
    try:
        return float(bond.get("bonus", 0)) > 0
    except (TypeError, ValueError):
        return False


def _best_percent(equip: Mapping, servant: Mapping) -> float:
    bond = equip.get("bond") or {}
    if bond.get("bonus_type") != "percent":
        return 0.0
    target = str(bond.get("target") or "")
    if not any(target_matches(target, traits) for traits in servant_trait_variants(servant)):
        return 0.0
    return float(bond.get("bonus") or 0.0)


def team_bond_score(
    servants: Sequence[Mapping],
    equips: Sequence[Mapping],
    bond_base: int = 1200,
) -> int:
    """计算五名本地从者的总羁绊；助战必须由调用者提前排除。"""
    if int(bond_base) <= 0:
        raise ValueError("bond_base must be positive")
    flat = sum(
        float((equip.get("bond") or {}).get("bonus") or 0)
        for equip in equips
        if (equip.get("bond") or {}).get("bonus_type") == "flat_per_servant"
    )
    total = 0
    for servant in servants:
        slot = int(servant.get("slot", 5))
        intermediate = math.floor(int(bond_base) * (1.2 if slot < 3 else 1.0))
        percent = sum(_best_percent(equip, servant) for equip in equips)
        total += math.floor(intermediate * (1.0 + percent / 100.0)) + math.floor(flat)
    return int(total)


def marginal_equip_gain(
    servants: Sequence[Mapping],
    fixed_equips: Sequence[Mapping],
    equip: Mapping,
    bond_base: int,
) -> int:
    before = team_bond_score(servants, fixed_equips, bond_base)
    after = team_bond_score(servants, [*fixed_equips, equip], bond_base)
    return after - before


def optimize_equips(
    servants: Sequence[Mapping],
    fixed_equips: Sequence[Mapping],
    candidates: Sequence[Mapping],
    max_new_slots: int,
    cost_budget: int,
    bond_base: int = 1200,
    beam_width: int = 500,
) -> EquipPlan:
    """以受限束搜索选择唯一礼装组合。

    最终排序先看总羁绊，再看更低 COST、更少礼装，最后按 ID 稳定决定。
    """
    max_new_slots = max(0, int(max_new_slots))
    cost_budget = max(0, int(cost_budget))
    base_score = team_bond_score(servants, fixed_equips, bond_base)
    usable = []
    fixed_ids = {str(item.get("id")) for item in fixed_equips}
    for equip in candidates:
        eid = str(equip.get("id") or "")
        if not eid or eid in fixed_ids or not equip_is_permanent_bond(equip):
            continue
        try:
            cost = int(equip.get("cost"))
        except (TypeError, ValueError):
            continue
        if cost < 0 or cost > cost_budget:
            continue
        gain = marginal_equip_gain(servants, fixed_equips, equip, bond_base)
        if gain > 0:
            usable.append((gain, eid, cost, dict(equip)))
    usable.sort(key=lambda item: (-item[0], item[2], item[1]))

    states = [(tuple(), 0, base_score)]
    for _gain, _eid, equip_cost, equip in usable:
        additions = []
        for selected, used, _score in states:
            if len(selected) >= max_new_slots or used + equip_cost > cost_budget:
                continue
            new_selected = (*selected, equip)
            score = team_bond_score(servants, [*fixed_equips, *new_selected], bond_base)
            additions.append((new_selected, used + equip_cost, score))
        states.extend(additions)
        # 相同 (数量, COST) 只保留一小组高分向量，避免候选数增长失控。
        states.sort(
            key=lambda state: (
                -state[2], state[1], len(state[0]),
                tuple(str(item.get("id")) for item in state[0]),
            )
        )
        states = states[: max(1, int(beam_width))]

    best = min(
        states,
        key=lambda state: (
            -state[2], state[1], len(state[0]),
            tuple(str(item.get("id")) for item in state[0]),
        ),
    )
    return EquipPlan(tuple(best[0]), int(best[1]), int(best[2]))


def rank_servants(
    candidates: Sequence[Mapping],
    current_servants: Sequence[Mapping],
    fixed_equips: Sequence[Mapping],
    equip_candidates: Sequence[Mapping],
    empty_equip_slots: int,
    cost_budget: int,
    bond_base: int = 1200,
) -> list[dict]:
    """对同一星级、已确认拥有的从者进行确定性排序。"""
    ranked = []
    baseline = team_bond_score(current_servants, fixed_equips, bond_base)
    for raw in candidates:
        servant = dict(raw)
        try:
            servant_cost = int(servant.get("cost"))
        except (TypeError, ValueError):
            continue
        if servant_cost > cost_budget:
            continue
        servants = [*current_servants, servant]
        plan = optimize_equips(
            servants,
            fixed_equips,
            equip_candidates,
            empty_equip_slots,
            cost_budget - servant_cost,
            bond_base,
        )
        direct_score = team_bond_score(servants, fixed_equips, bond_base)
        matched = sum(
            1 for equip in plan.equips if _best_percent(equip, servant) > 0
        )
        ranked.append({
            "servant": servant,
            "plan": plan,
            "gain": plan.score - baseline,
            "direct_score": direct_score,
            "matched_equips": matched,
            "remaining_cost": cost_budget - servant_cost - plan.cost,
        })
    ranked.sort(
        key=lambda item: (
            -item["gain"],
            -item["matched_equips"],
            -item["remaining_cost"],
            str(item["servant"].get("id")),
        )
    )
    return ranked
