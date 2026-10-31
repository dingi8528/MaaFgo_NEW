"""库存异常输入不得生成可覆盖旧库的完整结果。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent/custom"))
from inventory_scan_action import BuildPlayerInventory
import inventory_scan_action as inventory


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

    def test_equip_custom_appearances_share_one_inventory_identity(self):
        rng = np.random.default_rng(2173)
        names = ["f_94083800.png", "f_94083800_1_1_1_1.png"]
        templates = {name: rng.integers(0, 255, (56, 147, 3), dtype=np.uint8)
                     for name in names}
        self.scan.equip_list_dirs = []
        self.scan._read_first_template = lambda _dirs, name: templates.get(name)
        matrix, variants, covered, missing = self.scan._prepare_equip_features([
            {"id": "9408380", "images": names + names},
            {"id": "missing", "images": ["unreadable.png"]},
        ])
        self.assertEqual(covered, 1)
        self.assertEqual(missing, ["missing"])
        self.assertEqual(variants, [("9408380", name) for name in names])
        hits = self.scan._match_cells(
            None, matrix, variants, lambda _frame: ([matrix[1]], [(100, 200)]),
            0.9, 0.1,
        )
        self.assertEqual(hits["9408380"][2], names[1])
        self.assertEqual(len(self.scan.equip_full_templates), 2)

    def test_equip_legacy_filename_fallback_without_images(self):
        rng = np.random.default_rng(109)
        self.scan.equip_list_dirs = []
        image = rng.integers(0, 255, (56, 147, 3), dtype=np.uint8)
        self.scan._read_first_template = lambda _dirs, name: (
            image if name == "f_94010700.png" else None
        )
        matrix, variants, covered, missing = self.scan._prepare_equip_features([
            {"id": "9401070"}
        ])
        self.assertEqual((covered, missing), (1, []))
        self.assertEqual(variants, [("9401070", "f_94010700.png")])
        self.assertEqual(matrix.shape[0], 1)

    def make_single_row_equips(self, count):
        scan = self.scan
        scan.bond_equips_only = True
        scan.sx = scan.sy = 1.0
        scan.rarity_dirs = [str(
            Path(__file__).resolve().parents[1] /
            "assets/resource/base/image/个人库存/稀有度"
        )]
        scan._load_rarity_anchor()
        stars = scan._read_first_template(scan.rarity_dirs, "rarity4_0.png")
        rng = np.random.default_rng(408)
        source = rng.integers(0, 255, (56, 147, 3), dtype=np.uint8)
        scan.equip_list_dirs = []
        with patch.object(scan, "_read_first_template", return_value=source):
            matrix, variants, _, _ = scan._prepare_equip_features([{"id": "9400010"}])
        template = scan.equip_full_templates["f_94000100.png"]
        for column in range(count):
            x = inventory.EQUIP_FACE_X[column]
            self.frame[214:256, x:x + 110] = template
            x = inventory.INVENTORY_CARD_X[column] + 60
            height, width = stars.shape[:2]
            self.frame[291:291 + height, x:x + width] = stars
        return matrix, variants, stars

    def test_single_row_bond_equips_recognizes_sparse_and_full_rows(self):
        for count in (1, 3, 8):
            with self.subTest(count=count):
                self.frame.fill(0)
                matrix, variants, _ = self.make_single_row_equips(count)
                self.scan._shot = lambda: self.frame
                self.scan._scroll_thumb_center = lambda _image: None
                with patch("inventory_scan_action.time.sleep"):
                    observed, metrics = self.scan._scan_pages(
                        "礼装", [], matrix, variants, self.scan._stable_equip_hits, "swipe", 8
                    )
                self.assertEqual(set(observed), {"9400010"})
                self.assertEqual(metrics["bottom_detection"], "single_row")
                self.assertTrue(metrics["recognition_valid"])
                self.assertEqual(metrics["swipes"], 3)
                self.assertEqual(self.scan.last_rarity_grid["card_origins"], [190])

    def test_single_row_bond_equips_requires_no_lower_star_rows(self):
        _, _, stars = self.make_single_row_equips(1)
        height, width = stars.shape[:2]
        # 下方即使只有一张缺身份模板的礼装，也不能当成单行完整库存。
        self.frame[440:440 + height, 143:143 + width] = stars
        self.assertIsNone(self.scan._single_row_bond_equip_candidate(self.frame))

    def test_single_row_bond_equips_requires_top_row_and_bond_filter(self):
        self.make_single_row_equips(1)
        self.scan.bond_equips_only = False
        self.assertIsNone(self.scan._single_row_bond_equip_candidate(self.frame))
        self.scan.bond_equips_only = True
        shifted = np.roll(self.frame, 30, axis=0)
        self.assertIsNone(self.scan._single_row_bond_equip_candidate(shifted))

    def test_single_row_bond_equips_zero_identity_hits_does_not_complete(self):
        matrix, variants, _ = self.make_single_row_equips(1)
        self.scan._shot = lambda: self.frame
        self.scan._direct_equip_hits = lambda _hits, _image: {}
        with patch("inventory_scan_action.time.sleep"):
            result = self.scan._scan_pages(
                "礼装", [], matrix, variants, self.scan._stable_equip_hits, "swipe", 8
            )
        self.assertEqual(result, (None, None))
        self.scan._run_pipeline.assert_not_called()

    def test_single_row_bond_equips_requires_both_frames(self):
        matrix, variants, _ = self.make_single_row_equips(1)
        self.scan._shot = Mock(side_effect=[self.frame, self.frame, np.zeros_like(self.frame)])
        with patch("inventory_scan_action.time.sleep"):
            hits, _image = self.scan._stable_equip_hits([], matrix, variants)
        self.assertEqual(hits, {})
        self.assertFalse(self.scan.stable_single_row_equips)

    def test_single_row_bond_equips_with_mid_list_scrollbar_does_not_complete(self):
        matrix, variants, _ = self.make_single_row_equips(1)
        self.scan._shot = lambda: self.frame
        self.scan._scroll_thumb_center = lambda _image: 300
        with patch("inventory_scan_action.time.sleep"):
            result = self.scan._scan_pages(
                "礼装", [], matrix, variants, self.scan._stable_equip_hits, "swipe", 8
            )
        self.assertEqual(result, (None, None))

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
