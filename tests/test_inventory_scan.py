"""库存异常输入不得生成可覆盖旧库的完整结果。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent/custom"))
from inventory_scan_action import BuildPlayerInventory


class InventoryScanTests(unittest.TestCase):
    def setUp(self):
        self.scan = BuildPlayerInventory()
        self.scan.context = SimpleNamespace(tasker=SimpleNamespace(stopping=False))
        self.scan._ensure_current_icon_layout = lambda: True
        self.scan._visible_servant_features = lambda image: ([1] * 24, [(i, 200) for i in range(24)])
        self.scan._run_pipeline = Mock(return_value=True)
        self.scan._leave_current_list = Mock(return_value=True)
        self.scan._focus = lambda *args: None
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.hits = {"100100": (0.95, (200, 300), "face.png")}

    def run_scan(self, thumb, hits=None):
        self.scan._scroll_thumb_center = lambda image: thumb
        matcher = Mock(return_value=(self.hits if hits is None else hits, self.frame))
        with patch("inventory_scan_action.time.sleep"):
            result = self.scan._scan_pages("从者", [], None, [], matcher, "swipe", 8)
        return result, matcher

    def test_visible_but_zero_hits_retries_without_swiping(self):
        result, matcher = self.run_scan(300, {})
        self.assertEqual(result, (None, None))
        self.assertEqual(matcher.call_count, 2)
        self.scan._run_pipeline.assert_not_called()

    def test_stationary_mid_list_is_not_bottom_even_when_ids_match(self):
        result, _ = self.run_scan(300)
        self.assertEqual(result, (None, None))
        self.assertEqual(self.scan._run_pipeline.call_count, 3)

    def test_missing_scrollbar_is_not_proof_of_short_or_empty_list(self):
        self.assertEqual(self.run_scan(None)[0], (None, None))
        self.assertEqual(self.run_scan(None, {})[0], (None, None))

    def test_reliable_bottom_returns_observed_inventory(self):
        (observed, metrics), _ = self.run_scan(670)
        self.assertEqual(observed, self.hits)
        self.assertTrue(metrics["bottom_confirmed"])
        self.assertTrue(metrics["recognition_valid"])
        self.scan._leave_current_list.assert_called_once()

    def test_later_unrecognized_page_aborts_instead_of_omitting_it(self):
        self.scan._scroll_thumb_center = lambda image: 400
        matcher = Mock(side_effect=[(self.hits, self.frame), ({}, self.frame), ({}, self.frame)])
        with patch("inventory_scan_action.time.sleep"):
            result = self.scan._scan_pages("从者", [], None, [], matcher, "swipe", 8)
        self.assertEqual(result, (None, None))

    def test_run_does_not_write_when_scan_is_incomplete(self):
        scan = self.scan
        scan.context.get_node_data = lambda name: {"attach": {"scan_equips": False}}
        scan.context.tasker.controller = object()
        for name in ("_init_paths", "_init_scale", "_load_rarity_anchor", "_restore_ui"):
            setattr(scan, name, Mock())
        scan.image_roots = []
        scan._in_inventory_overview = lambda: True
        scan._build_servant_inventory = lambda: None
        scan._atomic_write_json = Mock()
        result = scan.run(scan.context, SimpleNamespace(node_name="scan"))
        self.assertFalse(result.success)
        scan._atomic_write_json.assert_not_called()


if __name__ == "__main__":
    unittest.main()
