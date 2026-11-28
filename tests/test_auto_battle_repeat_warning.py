"""原生连续战斗遇到可恢复的参数错误时记录告警并继续。"""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "agent/custom")]

import auto_battle_repeat_action as repeat


class RepeatWarningTests(unittest.TestCase):
    @patch.object(repeat.mfaalog, "warning")
    def test_invalid_reset_nodes_type_logs_warning(self, warning):
        nodes = repeat._parse_reset_hit_nodes({"reset_hit_nodes": "bad"})
        self.assertEqual(nodes, repeat._DEFAULT_RESET_HIT_NODES)
        warning.assert_called_once()

    @patch.object(repeat.mfaalog, "warning")
    def test_non_string_reset_nodes_are_filtered_with_warning(self, warning):
        nodes = repeat._parse_reset_hit_nodes({"reset_hit_nodes": ["a", 1, ""]})
        self.assertEqual(nodes, ["a"])
        warning.assert_called_once()

    @patch.object(repeat.mfaalog, "warning")
    def test_attach_read_failure_logs_warning_and_continues(self, warning):
        class ReachedBattleCount(Exception):
            pass

        context = Mock()
        context.get_node_data.side_effect = RuntimeError("读取失败")
        argv = SimpleNamespace(custom_action_param="{}")
        with patch.object(repeat, "_parse_battle_count", side_effect=ReachedBattleCount):
            with self.assertRaises(ReachedBattleCount):
                repeat.AutoBattleRepeatAction()._run_session(context, argv, 1, 1)
        warning.assert_called_once()
        self.assertIn("读取节点 attach 失败", warning.call_args.args[0])
