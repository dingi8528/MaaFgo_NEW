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
        self.scan._visible_servant_features = lambda image, row_origins=None: (
            [1] * 24, [(i, 200) for i in range(24)]
        )
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

    def test_servant_grid_uses_portrait_hits_instead_of_extra_false_row(self):
        scan = self.scan
        wrong = {
            "phase": 96, "rows": [(197, 5, 0.9)] * 4,
            "support": 19, "score_sum": 3.6, "origins": [96],
            "diagnostic": {"card_origins": [96]},
        }
        correct = {
            "phase": 41, "rows": [(291, 8, 0.96)] * 3,
            "support": 24, "score_sum": 2.88, "origins": [41],
            "diagnostic": {"card_origins": [41]},
        }
        scan._small_icon_row_candidates = lambda _image: [wrong, correct]
        scan._visible_servant_features = lambda _image, origins: ([], [origins[0]])

        def match(image, matrix, variants, extractor, threshold, margin):
            phase = extractor(image)[1][0]
            return {str(i): (0.8, (i, 200), "face.png")
                    for i in range(24 if phase == 41 else 2)}

        scan._match_cells = match
        hits = scan._match_servant_image(self.frame, None, [])
        self.assertEqual(len(hits), 24)
        self.assertEqual(scan.last_rarity_grid["card_origins"], [41])

    def test_equip_grid_prefers_full_template_hits_over_false_row(self):
        scan = self.scan
        wrong = {
            "phase": 96, "rows": [(197, 8, 0.9)] * 4,
            "support": 32, "score_sum": 3.6, "origins": [96],
            "diagnostic": {"card_origins": [96]},
        }
        correct = {
            "phase": 41, "rows": [(291, 8, 0.96)] * 3,
            "support": 24, "score_sum": 2.88, "origins": [41],
            "diagnostic": {"card_origins": [41]},
        }
        scan._small_icon_row_candidates = lambda _image: [wrong, correct]
        scan._visible_equip_features = lambda _image, origins: ([], [origins[0]])

        def match(image, matrix, variants, extractor, threshold, margin):
            phase = extractor(image)[1][0]
            prefix, count = ("correct", 10) if phase == 41 else ("wrong", 20)
            return {f"{prefix}-{i}": (0.9, (i, 200), "equip.png")
                    for i in range(count)}

        scan._match_cells = match
        scan._direct_equip_hits = lambda hits, _image: {
            item_id: hit for item_id, hit in hits.items()
            if item_id.startswith("correct-")
        }
        hits = scan._match_equip_image(self.frame, None, [])
        self.assertEqual(len(hits), 10)
        self.assertEqual(scan.last_rarity_grid["card_origins"], [41])

    def test_stationary_mid_list_is_not_bottom_even_when_ids_match(self):
        result, _ = self.run_scan(300)
        self.assertEqual(result, (None, None))
        self.assertEqual(self.scan._run_pipeline.call_count, 3)

    def test_missing_scrollbar_is_not_proof_of_short_or_empty_list(self):
        self.assertEqual(self.run_scan(None)[0], (None, None))
        self.assertEqual(self.run_scan(None, {})[0], (None, None))

    def test_tall_servant_scroll_thumb_can_confirm_bottom(self):
        frame = self.frame.copy()
        frame[592:709, 1230:1251] = 255  # 实机白色滑块约 21×117px。
        self.assertEqual(self.scan._scroll_thumb_center(frame), 650)
        self.assertEqual(self.run_scan(650)[0][1]["bottom_detection"], "scrollbar")

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
