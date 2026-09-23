import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent" / "custom"))
sys.path.insert(0, str(ROOT / "agent"))

from maa.custom_action import CustomAction  # noqa: E402
from bond_completion_action import CompleteBondFormation  # noqa: E402
from current_bond_completion_action import CompleteCurrentBondFormation  # noqa: E402


class CurrentBondCompletionTest(unittest.TestCase):
    def test_new_action_reuses_existing_engine(self):
        self.assertTrue(issubclass(CompleteCurrentBondFormation, CompleteBondFormation))

    def test_empty_expected_has_no_chaldea_protected_slots(self):
        expected = CompleteCurrentBondFormation._empty_expected()

        self.assertEqual(len(expected), 6)
        self.assertEqual([item["slot"] for item in expected], list(range(6)))
        self.assertTrue(all(item["kind"] == "EMPTY" for item in expected))
        self.assertTrue(all(item["equip_id"] is None for item in expected))
        self.assertTrue(all(item["grand_svt"] is False for item in expected))

    def test_fillable_slots_only_complete_five_owned_servants(self):
        detected = [
            {"kind": "OTHER"},
            {"kind": "EMPTY"},
            {"kind": "SUPPORT"},
            {"kind": "EMPTY"},
            {"kind": "OTHER"},
            {"kind": "EMPTY"},
        ]

        self.assertEqual(
            CompleteCurrentBondFormation._fillable_current_slots(detected, 2),
            [1, 3, 5],
        )
        self.assertEqual(
            CompleteCurrentBondFormation._fillable_current_slots(detected, 4),
            [1],
        )
        self.assertEqual(
            CompleteCurrentBondFormation._fillable_current_slots(detected, 5),
            [],
        )

    def test_task_options_are_isolated_and_safe_by_default(self):
        options = json.loads(
            (ROOT / "assets/options/当前编队羁绊补齐.json").read_text(
                encoding="utf-8"
            )
        )["option"]
        task = json.loads(
            (ROOT / "assets/tasks/当前编队羁绊补齐.json").read_text(
                encoding="utf-8"
            )
        )["task"][0]
        pipeline = json.loads(
            (ROOT / "assets/resource/base/pipeline/当前编队羁绊补齐.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(task["entry"], "当前编队羁绊补齐")
        self.assertNotIn("自动修改其他位置从者", task["option"])
        self.assertEqual(
            options["当前编队是否修改所有礼装"]["default_case"], "No"
        )
        attach = pipeline["当前编队羁绊补齐"]["attach"]
        self.assertIs(attach["modify_all_equips"], False)
        self.assertNotIn("chaldea_import_source", attach)
        self.assertEqual(
            pipeline["当前编队羁绊补齐"]["action"]["param"]["custom_action"],
            "complete_current_bond_formation",
        )

    def test_safe_restore_remains_a_failed_standalone_task(self):
        action = CompleteCurrentBondFormation.__new__(CompleteCurrentBondFormation)
        with patch.object(
            CompleteBondFormation,
            "_abort_safe",
            return_value=CustomAction.RunResult(success=True),
        ):
            result = action._abort_safe("recognition failed")

        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
