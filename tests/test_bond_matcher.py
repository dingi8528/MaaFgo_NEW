import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent" / "custom"))

from bond_matcher import (  # noqa: E402
    optimize_equips,
    rarity_order,
    target_matches,
    team_bond_score,
)


def servant(sid, slot, *tags, cost=7):
    return {"id": sid, "slot": slot, "cost": cost, "bond": {"tags": list(tags)}}


def equip(eid, bonus_type, bonus, target="all", cost=12):
    return {
        "id": eid,
        "cost": cost,
        "bond": {"bonus_type": bonus_type, "bonus": bonus, "target": target},
    }


class BondMatcherTest(unittest.TestCase):
    def test_rarity_order_is_stable_and_deduplicated(self):
        self.assertEqual(rarity_order(3), [3, 5, 4, 2, 1, 0])
        self.assertEqual(rarity_order(5), [5, 4, 3, 2, 1, 0])

    def test_composite_targets(self):
        traits = {"lawful", "good", "female", "saber_class", "star_power"}
        self.assertTrue(target_matches("lawful_good", traits))
        self.assertTrue(target_matches("lawful_female", traits))
        self.assertTrue(target_matches("star_or_evil", traits))
        self.assertFalse(target_matches("chaotic_seven", traits))

    def test_support_is_excluded_by_caller_and_front_bonus_is_floor_first(self):
        own = [servant("1", 0, "lawful", "good"), servant("2", 3, "evil")]
        lunch = equip("10", "percent", 10)
        self.assertEqual(team_bond_score(own, [lunch], 1200), 1584 + 1320)

    def test_flat_bonus_can_beat_small_percent_at_default_base(self):
        own = [servant("1", 0, "lawful")]
        flat = equip("10", "flat_per_servant", 50, cost=9)
        small = equip("11", "percent", 2, cost=9)
        plan = optimize_equips(own, [], [small, flat], 1, 9, 1200)
        self.assertEqual(plan.equips[0]["id"], "10")

    def test_optimizer_respects_cost_and_unique_candidates(self):
        own = [servant("1", 0, "lawful", "good")]
        all_10 = equip("10", "percent", 10, cost=12)
        lawful_20 = equip("11", "percent", 20, "lawful_good", cost=12)
        flat = equip("12", "flat_per_servant", 50, cost=9)
        plan = optimize_equips(own, [], [all_10, lawful_20, flat], 2, 21, 1200)
        self.assertEqual([item["id"] for item in plan.equips], ["11", "12"])
        self.assertEqual(plan.cost, 21)


if __name__ == "__main__":
    unittest.main()
