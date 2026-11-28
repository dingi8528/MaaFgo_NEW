"""Interpret empty slots and Laplace replay positions in Chaldea teams."""

SUPPORT_TYPES = {"friend", "fixed", "npc"}


def is_empty_member(member: object) -> bool:
    """A role alone does not fill a slot. Keep intentional CE-only support."""
    if member is None:
        return True
    if not isinstance(member, dict):
        return False
    sid = member.get("svtId")
    if sid is not None and not (type(sid) is int and sid == 0):
        return False
    role = str(member.get("supportType") or "").lower()
    if role not in SUPPORT_TYPES:
        return not member
    if role != "friend":
        return True
    equip1 = member.get("equip1")
    first_id = equip1.get("id") if isinstance(equip1, dict) else None
    if any(isinstance(member.get(key), dict) and member[key].get("candidates")
           for key in ("equip1", "equip2", "equip3")):
        return False  # Keep explicit requirements so invalid ones are reported.
    if any(type(value) is int and value > 0 for value in (first_id, member.get("ceId"))):
        return False
    if member.get("grandSvt") is not True:
        return True
    equip3 = member.get("equip3")
    board = member.get("classBoardData")
    return not (
        isinstance(equip3, dict) and type(equip3.get("id")) is int and equip3["id"] > 0
        or isinstance(board, dict) and type(board.get("grandBondEquipSkillChange")) is bool
    )


def laplace_team_order(share: dict, roster) -> tuple[tuple[int, ...], tuple[int, ...]] | None:
    """Return original team slots in Laplace's starting and reserve order."""
    # Local editor and BBC actions already use the UI's fixed positions.
    if (roster is None or share.get("_source") == "bbc"
            or not all(type(share.get(key)) is int for key in ("minBuild", "appBuild"))):
        return None
    starting = tuple(index for index, member in enumerate(roster) if member is not None)[:3]
    if not starting:
        return None
    # Laplace draws the first three servants from the party, skipping empty
    # slots as it draws. Unconsumed slots retain their relative positions.
    backup_start = starting[-1] + 1 if len(starting) == 3 else 6
    backup = tuple(range(backup_start, 6))
    if starting == (0, 1, 2) and backup == (3, 4, 5):
        return None
    return starting, backup


def laplace_replay_slots(
    share: dict, roster: tuple[str | None, ...] | None,
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]] | None, tuple[str | None, ...] | None]:
    """Map simulator slots to the battle UI and return its initial roster."""
    order = laplace_team_order(share, roster)
    if order is None:
        return None, roster
    starting, backup = order
    # If reserves are promoted at entry, the full frontline follows team order.
    if starting[-1] >= 3:
        display = list(roster)
        display[:3] = [roster[index] for index in starting] + [None] * (3 - len(starting))
        backup_start = backup[0] if backup else 6
        display[3:backup_start] = [None] * (backup_start - 3)
        return (tuple(range(len(starting))), backup), tuple(display)
    return order, roster
