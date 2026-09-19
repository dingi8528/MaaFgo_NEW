"""将 BBchannel/settings 的队伍配置导入为本地 BattleShareData。

只转换可以确定含义的队伍与回合动作。选卡策略暂时跳过；
条件分支和专属技能无法表示时拒绝生成误导性的攻略。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .servant_types import MYSTIC_CODE_ID_TO_BBC_SN, ORDER_CHANGE_MYSTIC_CODE_IDS


ROOT = Path(__file__).resolve().parents[2]
_ROUND_KEY = re.compile(r"round(\d+)_turns$")
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class BbcImportError(ValueError):
    """BBC 配置无法可靠转换。"""


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BbcImportError(f"读取 JSON 失败: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BbcImportError(f"JSON 顶层必须是对象: {path}")
    return data


def _catalogs(root: Path, server: str) -> tuple[dict, dict]:
    server = {"CH": "CH", "CN": "CH", "JP": "JP", "CNTW": "CNTW"}.get(server, "CH")
    servant_file = root / "BBchannel" / f"servant_info_{server}.json"
    if not servant_file.is_file():
        raise BbcImportError(f"缺少 BBC 从者资料: {servant_file}")
    servants = _read_json(servant_file)
    equip_file = root / "agent" / "utils" / "Chaldea" / "equip_names_CN.json"
    equips = _read_json(equip_file) if equip_file.is_file() else {}
    return servants, equips


def _servant_id(name: str, catalog: dict, slot: int) -> int:
    item = catalog.get(name)
    if not isinstance(item, dict):
        aliases = [value for value in catalog.values()
                   if isinstance(value, dict) and name in (value.get("other_name") or [])]
        if len(aliases) == 1:
            item = aliases[0]
    sn = item.get("SN") if isinstance(item, dict) else None
    if not isinstance(sn, (str, int)) or not str(sn).isdigit() or int(sn) <= 0:
        raise BbcImportError(f"槽位 {slot} 的从者“{name}”无法唯一匹配 BBC 从者 ID")
    return int(sn)


def _equip_ids(value: object, equips: dict) -> tuple[list[int | None], list[str]]:
    warnings: list[str] = []
    by_name: dict[str, list[int]] = {}
    for key, name in equips.items():
        if str(key).isdigit() and isinstance(name, str):
            by_name.setdefault(name, []).append(int(key))
    if isinstance(value, str):
        names: list[object] = [value]
    elif isinstance(value, list):
        names = value[:3]
    else:
        return [None, None, None], warnings
    result: list[int | None] = [None, None, None]
    for index, raw in enumerate(names):
        if isinstance(raw, list):
            if not raw:
                continue
            if len(raw) != 1:
                warnings.append(f"助战礼装第 {index + 1} 格有多个候选，未导入")
                continue
            raw = raw[0]
        if not isinstance(raw, str) or not raw.strip():
            continue
        ids = by_name.get(raw.strip(), [])
        if len(ids) == 1:
            result[index] = ids[0]
        else:
            warnings.append(f"助战礼装“{raw}”无法唯一匹配 Chaldea 礼装 ID，未导入")
    return result, warnings


def _support_levels(config: dict, support: dict, warnings: list[str]) -> None:
    skills = config.get("skillsLevel")
    if skills is not None:
        if (isinstance(skills, list) and 3 <= len(skills) <= 8
                and all(type(value) is int and 0 <= value <= 10 for value in skills)):
            support["skillLvs"] = skills[:3]
            support["appendLvs"] = (skills[3:] + [0] * 5)[:5]
        else:
            warnings.append("助战技能等级筛选值无效，未导入")
    for source_key, target_key, maximum in (
        ("NPlevel", "tdLv", 5),
        ("servantLevel", "lv", 130),
    ):
        value = config.get(source_key)
        if value is None:
            continue
        if type(value) is int and 0 <= value <= maximum:
            support[target_key] = value
        else:
            warnings.append(f"助战 {source_key} 筛选值无效，未导入")


def _skill_action(raw: object, mystic_code_id: int, swaps: list[list[int]],
                  location: str) -> dict:
    target = None
    number = raw
    if isinstance(raw, list):
        if len(raw) == 3 and raw[0] == 12 and all(type(n) is int for n in raw[1:]):
            if mystic_code_id not in ORDER_CHANGE_MYSTIC_CODE_IDS:
                raise BbcImportError(f"{location}: 配置了换人，但魔术礼装不是换人服")
            a, b = raw[1:]
            front, back = (a, b) if 1 <= a <= 3 and 4 <= b <= 6 else (b, a)
            if not (1 <= front <= 3 and 4 <= back <= 6):
                raise BbcImportError(f"{location}: 换人槽位无效: {raw}")
            swaps.append([front - 1, back - 1])
            return {"type": "skill", "svt": None, "skill": 2}
        if len(raw) != 2 or not all(type(n) is int for n in raw):
            raise BbcImportError(f"{location}: 不支持的 BBC 特殊技能 {raw}")
        number, target = raw
        if not 1 <= target <= 3:
            raise BbcImportError(f"{location}: 技能目标必须是前排 1～3 号位: {raw}")
    if type(number) is not int or not 1 <= number <= 12:
        raise BbcImportError(f"{location}: 不支持的 BBC 技能 {raw}")
    if number == 12 and mystic_code_id in ORDER_CHANGE_MYSTIC_CODE_IDS:
        raise BbcImportError(f"{location}: 换人技能缺少首发和候补槽位")
    action = {
        "type": "skill",
        "svt": (number - 1) // 3 if number <= 9 else None,
        "skill": (number - 1) % 3 if number <= 9 else number - 10,
    }
    if target is not None:
        action["options"] = {"playerTarget": target - 1}
    return action


def convert_bbc_config(config: dict, catalog: dict, equips: dict) -> tuple[dict, list[str]]:
    """转换 BBC 配置；无法精确表达的动作直接失败。"""
    if not isinstance(config, dict):
        raise BbcImportError("BBC 配置顶层必须是对象")
    warnings: list[str] = []
    reverse_codes = {sn: code for code, sn in MYSTIC_CODE_ID_TO_BBC_SN.items()}
    sn = config.get("master_equip")
    if type(sn) is not int or sn not in reverse_codes:
        raise BbcImportError(f"无法识别魔术礼装 master_equip={sn!r}")
    mystic_code_id = reverse_codes[sn]

    slots: list[dict | None] = []
    for index in range(6):
        name = config.get(f"servant_{index}_name")
        if name is None or name == "":
            slots.append(None)
        elif isinstance(name, str):
            slots.append({"svtId": _servant_id(name, catalog, index + 1),
                          "supportType": "none"})
        else:
            raise BbcImportError(f"槽位 {index + 1} 的从者名无效: {name!r}")
    if not any(slots[:3]):
        raise BbcImportError("BBC 配置缺少前排从者")

    assist = config.get("assistIdx")
    if type(assist) is int and 0 <= assist < 6 and slots[assist] is not None:
        slots[assist]["supportType"] = "friend"
        _support_levels(config, slots[assist], warnings)
        assist_mode = config.get("assistMode")
        if assist_mode == "冠位助战":
            slots[assist]["grandSvt"] = True
        if assist_mode in ("从者礼装", "冠位助战"):
            equip_ids, equip_warnings = _equip_ids(config.get("assistEquip"), equips)
            warnings.extend(equip_warnings)
            for index, equip_id in enumerate(equip_ids, 1):
                if equip_id is not None:
                    slots[assist][f"equip{index}"] = {
                        "id": equip_id,
                        "limitBreak": config.get("fullEquip") == 1,
                    }
    elif assist is not None:
        warnings.append(f"助战索引 {assist!r} 没有对应从者，未标记助战")

    rounds = sorted(int(match.group(1)) for key in config
                    if (match := _ROUND_KEY.fullmatch(key)))
    if not rounds or rounds != list(range(1, max(rounds) + 1)):
        raise BbcImportError("BBC 波次 roundN_turns 缺失或不连续")
    actions: list[dict] = []
    swaps: list[list[int]] = []
    for round_no in rounds:
        turns = config[f"round{round_no}_turns"]
        if type(turns) is not int or turns < 1:
            raise BbcImportError(f"第 {round_no} 波回合数无效: {turns!r}")
        extra_skills = config.get(f"round{round_no}_extraSkill")
        if extra_skills:
            raise BbcImportError(f"第 {round_no} 波配置了额外技能，无法映射到固定回合")
        extra_strategy = config.get(f"round{round_no}_extraStrategy")
        if extra_strategy is not None:
            warnings.append(f"第 {round_no} 波额外选卡策略未导入")
        for turn_no in range(turns):
            prefix = f"round{round_no}_turn{turn_no}"
            condition = config.get(f"{prefix}_condition")
            if condition is not None:
                raise BbcImportError(f"{prefix}: 条件分支无法映射到固定回合")
            strategy = config.get(f"{prefix}_strategy")
            if strategy is not None:
                warnings.append(f"{prefix}: 自定义选卡策略未导入")
            skills = config.get(f"{prefix}_skill")
            nps = config.get(f"{prefix}_np")
            if not isinstance(skills, list) or not isinstance(nps, list):
                raise BbcImportError(f"{prefix}: 技能或宝具列表缺失")
            swaps_before = len(swaps)
            for raw in skills:
                actions.append(_skill_action(raw, mystic_code_id, swaps, prefix))
            if len(swaps) - swaps_before > 1:
                raise BbcImportError(f"{prefix}: 同一回合多次换人暂不支持")
            attacks = []
            for raw in nps:
                if type(raw) is not int or not 1 <= raw <= 3:
                    raise BbcImportError(f"{prefix}: 宝具槽位无效: {raw!r}")
                attacks.append({"isTD": True, "svt": raw - 1})
            actions.append({"type": "attack", "attacks": attacks})

    share = {
        "_source": "bbc",
        "team": {
            "mysticCode": {"mysticCodeId": mystic_code_id},
            "onFieldSvts": slots[:3],
            "backupSvts": slots[3:],
        },
        "actions": actions,
        "delegate": {"replaceMemberIndexes": swaps},
    }
    return share, warnings


def import_bbc_file(source: str, *, root: Path = ROOT) -> tuple[Path, list[str]]:
    """读取 settings 中的配置并生成 config/Battle 下可供现有流程读取的 JSON。"""
    settings = (root / "BBchannel" / "settings").resolve()
    if not source or not source.strip():
        raise BbcImportError("请选择 BBC 队伍配置")
    name = Path(source.strip()).name
    if name != source.strip() or name in (".", ".."):
        raise BbcImportError("BBC 配置只能选择 BBchannel/settings 下的文件名")
    if not name.lower().endswith(".json"):
        name += ".json"
    source_path = settings / name
    if not source_path.is_file():
        raise BbcImportError(f"BBC 配置不存在: {source_path}")
    if source_path.resolve().parent != settings:
        raise BbcImportError("BBC 配置必须位于 BBchannel/settings 内")
    raw = source_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    config = _read_json(source_path)
    catalog, equips = _catalogs(root, str(config.get("server") or "CH"))
    share, warnings = convert_bbc_config(config, catalog, equips)
    share["_bbcSource"] = {"file": name, "sha256": digest}
    if warnings:
        share["_conversionWarnings"] = warnings

    safe_stem = _INVALID_FILENAME.sub("_", source_path.stem).rstrip(" .")[:48] or "team"
    result_digest = hashlib.sha256(
        json.dumps(share, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    output = root / "config" / "Battle" / f"bbc_{safe_stem}_{result_digest[:12]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if _read_json(output) != share:
            raise BbcImportError(f"目标文件已存在且内容不同，请先处理: {output}")
        return output, warnings
    created = False
    try:
        with output.open("x", encoding="utf-8") as stream:
            created = True
            json.dump(share, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise
    return output, warnings


def import_bbc_all(*, root: Path = ROOT) -> tuple[
    list[tuple[str, Path, list[str]]], list[tuple[str, str]]
]:
    """逐个导入 settings 中的 JSON，单个配置失败时继续处理其余文件。"""
    settings = root / "BBchannel" / "settings"
    sources = sorted(settings.glob("*.json"), key=lambda path: path.name.casefold())
    if not sources:
        raise BbcImportError(f"未找到 BBC 队伍配置: {settings}")

    converted: list[tuple[str, Path, list[str]]] = []
    skipped: list[tuple[str, str]] = []
    for path in sources:
        try:
            output, warnings = import_bbc_file(path.name, root=root)
        except (BbcImportError, OSError) as exc:
            skipped.append((path.name, str(exc)))
        else:
            converted.append((path.name, output, warnings))
    return converted, skipped
