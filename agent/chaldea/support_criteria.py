"""将 Chaldea 队伍中明确标记的助战转换为助战筛选条件。"""

from .game_data import get_equip_name


_SUPPORT_TYPES = {"friend", "fixed", "npc"}
_FULLWIDTH_ALNUM = str.maketrans({
    codepoint: codepoint - 0xFEE0
    for start, end in ((0xFF10, 0xFF19), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A))
    for codepoint in range(start, end + 1)
})
_CLASS_TABS = {
    "saber": "剑士", "archer": "弓兵", "lancer": "枪兵", "rider": "骑兵",
    "caster": "魔术师", "assassin": "暗杀者", "berserker": "狂战士",
    "ruler": "OTHER", "avenger": "OTHER", "mooncancer": "OTHER",
    "alterego": "OTHER", "foreigner": "OTHER", "pretender": "OTHER",
    "shielder": "OTHER", "beast": "OTHER", "unbeast": "OTHER",
}


def _level(value, label, maximum):
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        raise ValueError(f"{label} 不是有效等级: {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 不是有效等级: {value!r}") from exc
    if not 0 <= number <= maximum:
        raise ValueError(f"{label} 超出范围: {number}")
    return number


def _levels(values, count, label):
    if values is None:
        values = []
    if not isinstance(values, list):
        raise ValueError(f"{label} 不是等级数组")
    return [_level(values[i], f"{label}{i + 1}", 10) if i < len(values) else 0
            for i in range(count)]


def _equip(item, source_slot, resolve_name, target_slot=None):
    """解析 Chaldea 礼装槽，并映射到 MaaFGO 可见卡面槽位。"""
    equip = item.get(f"equip{source_slot}")
    if isinstance(equip, dict) and equip.get("id") is not None:
        raw_id = equip["id"]
        limit_break = equip.get("limitBreak", False)
    elif source_slot == 1:
        raw_id = item.get("ceId")
        limit_break = item.get("ceLimitBreak", False)
    else:
        raw_id = None
        limit_break = False
    if raw_id in (None, "", 0):
        return None
    try:
        equip_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"助战第{source_slot}格礼装 ID 无效: {raw_id!r}") from exc
    if equip_id <= 0:
        raise ValueError(f"助战第{source_slot}格礼装 ID 无效: {equip_id}")
    name = resolve_name(equip_id)
    if not name:
        raise ValueError(f"助战第{source_slot}格礼装 {equip_id} 缺少名称数据")
    # Chaldea 名称库可能使用全角英数字（如“来自ＮＦＦ的爱”），而图片资源
    # 使用半角文件名。这里只转换英数字，不能用 NFKC 整体归一化；同时把
    # 名称中的路径分隔符转成全角符号，与可落盘的模板文件名保持一致。
    normalized_name = (str(name).translate(_FULLWIDTH_ALNUM)
                       .replace("/", "／").replace("\\", "＼"))
    return {
        "slot": target_slot if target_slot is not None else source_slot,
        "source_slot": source_slot,
        "id": equip_id,
        "name": f"{normalized_name}.png",
        "status": "满破" if limit_break is True else "非满破",
    }


def build_support_criteria(share_data, servant_map, resolve_name=get_equip_name):
    """返回现有 SupportAction 可使用的条件；不能可靠推断助战时失败。"""
    team = share_data.get("team") if isinstance(share_data, dict) else None
    if not isinstance(team, dict):
        raise ValueError("Chaldea 数据缺少 team")
    front, backup = team.get("onFieldSvts"), team.get("backupSvts")
    if not isinstance(front, list) or not isinstance(backup, list):
        raise ValueError("Chaldea 数据缺少有效的六槽队伍")
    members = (front[:3] + backup[:3])
    supports = [item for item in members if isinstance(item, dict)
                and str(item.get("supportType") or "").lower() in _SUPPORT_TYPES]
    if len(supports) != 1:
        raise ValueError(f"Chaldea 队伍必须恰有一个标记助战，实际为 {len(supports)} 个")
    support = supports[0]
    try:
        servant_id = int(support.get("svtId"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Chaldea 助战缺少有效 svtId") from exc
    if servant_id <= 0:
        raise ValueError("Chaldea 助战缺少有效 svtId")
    servant = servant_map.get(str(servant_id))
    if not servant or not servant.get("images"):
        raise ValueError(f"助战从者 {servant_id} 缺少头像资源")
    servant_class = str(servant.get("class") or "").lower()
    class_name = _CLASS_TABS.get(servant_class)
    if not class_name:
        raise ValueError(f"助战从者 {servant_id} 的职介无法识别")
    grand = support.get("grandSvt") is True
    if grand:
        # Chaldea 冠位槽定义：equip1=普通礼装、equip2=羁绊礼装、
        # equip3=冠位追加礼装。MaaFGO 的两张卡面模板对应 equip1/equip3；
        # equip2 只通过羁绊效果图标判断，不匹配礼装卡面。
        equips = [
            _equip(support, 1, resolve_name, target_slot=1),
            _equip(support, 3, resolve_name, target_slot=2),
        ]
        bond_equip = support.get("equip2")
        if isinstance(bond_equip, dict) and bond_equip.get("id") not in (None, "", 0):
            class_board = support.get("classBoardData")
            bond_changed = (class_board.get("grandBondEquipSkillChange")
                            if isinstance(class_board, dict) else None)
            if isinstance(bond_changed, bool):
                ce_bond = "50np" if bond_changed else "original"
            else:
                ce_bond = "any"
        else:
            ce_bond = "any"
    else:
        equips = [_equip(support, 1, resolve_name)]
        ce_bond = "any"
    return {
        "support_type": "grand" if grand else "normal",
        "servant_id": str(servant_id),
        "class_name": class_name,
        "images": servant["images"],
        "ce_specs": [equip for equip in equips if equip is not None],
        "active": _levels(support.get("skillLvs"), 3, "主动技能"),
        "passive": _levels(support.get("appendLvs"), 5, "追加技能"),
        "np_level": _level(support.get("tdLv"), "宝具等级", 5),
        "level": _level(support.get("lv"), "从者等级", 130),
        "ce_bond": ce_bond,
    }
