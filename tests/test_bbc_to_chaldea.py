"""BBC 设置导入到原生 Chaldea 战斗流程的离线回归测试。"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "agent" / "custom")]

from battle.data.chaldea_converter import convert_chaldea_actions_to_battle_plan
from battle.core.decider import RuleDecider
from battle.core.enums import Scene
from battle.core.models import (BattleAction, BattlePlan, BattleState, Confidence,
                                MasterSkillAction, OrderChangeAction,
                                ServantSkillAction, ServantState, SkillState,
                                TurnPlan)
from battle.core.policy import StrategyProfile
from battle.core.validator import (skip_unusable_servant_skills,
                                   validate_main_action)
from battle.runtime.runtime import AutoBattleRuntime
from chaldea.bbc_importer import (BbcImportError, _catalogs, _read_json,
                                  convert_bbc_config, import_bbc_all,
                                  import_bbc_file)
import chaldea


class BbcToChaldeaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.equips = _catalogs(ROOT, "CH")

    def _config(self, filename):
        return _read_json(ROOT / "BBchannel" / "settings" / filename)

    def test_standard_team_and_plan(self):
        share, warnings = convert_bbc_config(
            self._config("爱尔奎特_光狐_光狐.json"), self.catalog, self.equips,
        )
        self.assertFalse(warnings)
        self.assertEqual(share["team"]["onFieldSvts"][0]["svtId"], 2300500)
        plan = convert_chaldea_actions_to_battle_plan(
            share["actions"], share["delegate"],
            share["team"]["mysticCode"]["mysticCodeId"],
        )
        self.assertEqual(len(plan.turns), 3)
        self.assertEqual(plan.turns[0].np_order, (1,))
        self.assertEqual(plan.turns[0].skill_sequence[0].servant_slot, 1)

    def test_order_change_keeps_skill_order(self):
        share, _ = convert_bbc_config(
            self._config("C冠位-有珠_圣诞玛尔达_CBA_Caber.json"),
            self.catalog, self.equips,
        )
        plan = convert_chaldea_actions_to_battle_plan(
            share["actions"], share["delegate"],
            share["team"]["mysticCode"]["mysticCodeId"],
        )
        sequence = plan.turns[0].skill_sequence
        swap_index = next(i for i, action in enumerate(sequence)
                          if type(action).__name__ == "OrderChangeAction")
        self.assertEqual(sequence[swap_index - 1].skill_index, 3)
        self.assertEqual(sequence[swap_index].starting_member_idx, 2)
        self.assertEqual(sequence[swap_index].sub_member_idx, 4)
        self.assertGreater(len(sequence), swap_index + 1)

        runtime = AutoBattleRuntime.__new__(AutoBattleRuntime)
        runtime.decider = SimpleNamespace(plan=plan)
        runtime.battle_policy = SimpleNamespace(skill=SimpleNamespace(use_master_skills=True))
        calls = []
        runtime._execute_skill_cast = lambda label, *_args, **_kwargs: calls.append(label) or True
        runtime._wait_until = lambda *_args: True
        runtime._mark_action = lambda label: calls.append(label)
        runtime.executor = SimpleNamespace(order_change=lambda *_args: True)
        turn = plan.turns[0]
        action = BattleAction(
            target_enemy=None, picks=(), servant_skills=turn.servant_skills,
            master_skills=turn.master_skills, order_change=turn.order_change,
            skill_sequence=turn.skill_sequence,
        )
        self.assertTrue(runtime._execute_skills(action))
        self.assertEqual(calls[5:9], ["cast_master_skill", "order_change",
                                     "cast_master_skill", "cast_servant_skill"])

    def test_explicit_empty_np_turn_does_not_auto_cast_np(self):
        plan = BattlePlan(turns=(TurnPlan(np_order=()),))
        state = SimpleNamespace(
            scene=Scene.COMMAND_SELECTION, enemies=(), cards=(),
            np_cards=(SimpleNamespace(servant_slot=1),),
        )
        action = RuleDecider(plan=plan).decide(state)
        self.assertFalse(action.picks)

    def test_swap_uses_new_servant_skill_state(self):
        skill = ServantSkillAction(2, 1)
        master = MasterSkillAction(3)
        swap = OrderChangeAction(2, 4)
        action = BattleAction(
            target_enemy=None, picks=(), servant_skills=(skill, skill),
            master_skills=(master,), order_change=swap,
            skill_sequence=(skill, master, swap, skill),
        )
        unavailable = SkillState(False, Confidence(1.0))
        available = SkillState(True, Confidence(1.0))
        state = BattleState(
            scene=Scene.MAIN_BATTLE, scene_confidence=Confidence(1.0),
            cards=(), np_cards=(), enemies=(),
            servants=(ServantState(2, (unavailable, available, available),
                                   Confidence(1.0)),),
            master_skills=(available, available, available),
        )
        filtered, skipped = skip_unusable_servant_skills(action, state, StrategyProfile())
        self.assertEqual(len(skipped), 1)
        self.assertEqual(filtered.servant_skills, (skill,))
        self.assertEqual(filtered.skill_sequence, (master, swap, skill))
        self.assertTrue(validate_main_action(filtered, state, StrategyProfile()).ok)

    def test_unsupported_special_action_fails(self):
        with self.assertRaisesRegex(BbcImportError, "特殊技能"):
            convert_bbc_config(
                self._config("迪拜BB_棉被王_Caber_花嫁.json"),
                self.catalog, self.equips,
            )

    def test_card_strategy_is_recorded_and_skipped(self):
        config = self._config("爱尔奎特_光狐_光狐.json")
        config["round1_turn0_strategy"] = [{"card1": {"cards": ["1B"]}}]
        share, warnings = convert_bbc_config(config, self.catalog, self.equips)
        self.assertEqual(len(warnings), 1)
        self.assertTrue(share["actions"])

    def test_servant_only_support_does_not_require_default_equip(self):
        config = self._config("爱尔奎特_光狐_光狐.json")
        config["assistMode"] = "仅从者"
        share, _ = convert_bbc_config(config, self.catalog, self.equips)
        support = share["team"]["onFieldSvts"][config["assistIdx"]]
        self.assertNotIn("equip1", support)

    def test_support_level_filters_are_imported(self):
        config = self._config("C冠位-有珠_圣诞玛尔达_CBA_Caber.json")
        share, _ = convert_bbc_config(config, self.catalog, self.equips)
        support = share["team"]["backupSvts"][0]
        self.assertEqual(support["skillLvs"], config["skillsLevel"][:3])
        self.assertEqual(support["appendLvs"], config["skillsLevel"][3:8])
        self.assertEqual(support["tdLv"], config["NPlevel"])
        self.assertEqual(support["lv"], config["servantLevel"])

    def test_file_generation_is_idempotent_and_loader_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / "BBchannel" / "settings"
            settings.mkdir(parents=True)
            shutil.copy2(ROOT / "BBchannel" / "settings" / "爱尔奎特_光狐_光狐.json", settings)
            shutil.copy2(ROOT / "BBchannel" / "servant_info_CH.json", root / "BBchannel")
            data_dir = root / "agent" / "utils" / "Chaldea"
            data_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "agent" / "utils" / "Chaldea" / "equip_names_CN.json", data_dir)
            path, warnings = import_bbc_file("爱尔奎特_光狐_光狐.json", root=root)
            self.assertFalse(warnings)
            self.assertEqual(path.parent, root / "config" / "Battle")
            self.assertIsInstance(json.loads(path.read_text(encoding="utf-8"))["team"], dict)
            with patch.object(chaldea, "CACHE_DIR", str(path.parent)):
                loaded = chaldea._load_local_file(path.name)
            self.assertEqual(loaded["team"]["onFieldSvts"][0]["svtId"], 2300500)
            same, _ = import_bbc_file("爱尔奎特_光狐_光狐.json", root=root)
            self.assertEqual(path, same)
            with self.assertRaises(BbcImportError):
                import_bbc_file("../servant_info_CH.json", root=root)

    def test_all_configs_continue_after_rejected_file_and_reuse_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / "BBchannel" / "settings"
            settings.mkdir(parents=True)
            (settings / "a_bad.json").write_text("{}", encoding="utf-8")
            shutil.copy2(ROOT / "BBchannel/settings/爱尔奎特_光狐_光狐.json",
                         settings / "z_good.json")
            shutil.copy2(ROOT / "BBchannel/servant_info_CH.json", root / "BBchannel")
            data_dir = root / "agent/utils/Chaldea"
            data_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "agent/utils/Chaldea/equip_names_CN.json", data_dir)

            converted, skipped = import_bbc_all(root=root)
            self.assertEqual(len(converted), 1)
            self.assertEqual(converted[0][0], "z_good.json")
            self.assertTrue(converted[0][1].is_file())
            self.assertEqual(skipped[0][0], "a_bad.json")
            before = converted[0][1].read_bytes()
            again, skipped_again = import_bbc_all(root=root)
            self.assertEqual(again[0][1], converted[0][1])
            self.assertEqual(again[0][1].read_bytes(), before)
            self.assertEqual(skipped_again, skipped)


if __name__ == "__main__":
    unittest.main()
