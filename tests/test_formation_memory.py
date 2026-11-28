"""编队截图在匹配后可释放，模板缓存按任务与校准清理。"""
import gc
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

import cv2
import numpy as np

from formation_test_support import formation
from current_bond_completion_action import CompleteCurrentBondFormation


IMAGE_FIELDS = (
    "_tpl_scale_cache", "local_templates", "support_templates",
    "identity_templates", "equip_team_templates", "equip_list_templates", "equip_database",
    "support_marker", "edit_marker", "config_marker", "select_page_markers",
    "formation_confirm_marker", "equip_confirm_marker", "grand_equip_popup_marker",
)


class FormationMemoryTests(unittest.TestCase):
    def assert_match_releases_frames(self, action, screenshot):
        action.sx = action.sy = 1.0
        template = np.random.default_rng(42).integers(0, 256, (4, 4, 3), np.uint8)
        frames = []
        for _ in range(32):
            frame = screenshot()
            frame[7:11, 9:13] = template
            frames.append(weakref.ref(frame))
            score, center = action._match_template(frame, template, (6, 4, 16, 16))
            self.assertGreater(score, 0.99)
            self.assertEqual(center, (11, 9))
        del frame
        gc.collect()
        self.assertTrue(all(ref() is None for ref in frames))

    def test_match_releases_frames_passed_directly(self):
        self.assert_match_releases_frames(
            formation.AutoFormationFromChaldea(), lambda: np.zeros((32, 32, 3), np.uint8),
        )

    def test_current_bond_match_releases_synchronous_screenshots(self):
        action = CompleteCurrentBondFormation()
        frame_job = SimpleNamespace(get=lambda: np.zeros((32, 32, 3), np.uint8))
        action.controller = SimpleNamespace(post_screencap=lambda: SimpleNamespace(wait=lambda: frame_job))
        self.assert_match_releases_frames(action, action._shot)

    def test_match_returns_no_result_for_roi_outside_screen(self):
        action = formation.AutoFormationFromChaldea()
        action.sx = action.sy = 1.0
        frame = np.zeros((32, 32, 3), np.uint8)
        template = np.zeros((4, 4, 3), np.uint8)
        self.assertIsNone(action._match_template(frame, template, (32, 0, 16, 16)))

    @patch.object(formation, "fetch_share_data", return_value=({}, None, None))
    def test_run_releases_images(self, fetch):
        for action_type in (formation.AutoFormationFromChaldea, formation.ValidateFormationFromChaldea):
            for outcome in ("success", "missing", "exception"):
                with self.subTest(action=action_type.__name__, outcome=outcome):
                    action = action_type()
                    entered_clean = []

                    def read_node(name):
                        entered_clean.append(all(k not in vars(action) for k in IMAGE_FIELDS))
                        for key in IMAGE_FIELDS:
                            setattr(action, key, object())
                        if outcome == "exception":
                            raise RuntimeError("读取失败")
                        return {"attach": {
                            "chaldea_import_source": "" if outcome == "missing" else "team",
                            "auto_equip": False,
                        }}

                    for key in (*IMAGE_FIELDS, "context", "controller"):
                        setattr(action, key, object())
                    for name in (
                        "_begin_verified_formation_update", "_discard_unpublished_formation",
                        "_fail", "_init_paths", "_init_scale", "_prepare_target_templates",
                        "_log_layout", "_configure_support_target", "_confirmed_now",
                        "_relocate_unexpected_support", "_reorder_existing", "_replace_local_servants",
                        "_repair_trial_grand_slot", "_log_support_identity_if_possible",
                        "_run_pipeline", "_confirm_formation_change_if_present", "_ensure_mystic_code",
                        "_publish_verified_layout", "_manual_identities_match",
                    ):
                        setattr(action, name, Mock(return_value=True))
                    action._build_expected = Mock(return_value=[])
                    action._detect_slots_stable = Mock(return_value=[])
                    action._should_clear_formation = Mock(return_value=False)
                    action._first_mismatch = Mock(return_value=None)
                    action._wait_for_formation_page = Mock(return_value="confirm")
                    context = SimpleNamespace(get_node_data=read_node, tasker=SimpleNamespace(controller=object()))
                    result = action.run(context, SimpleNamespace(node_name="formation"))
                    self.assertEqual(result.success, outcome == "success")
                    self.assertEqual(entered_clean, [True])
                    for key in (*IMAGE_FIELDS, "context", "controller"):
                        self.assertNotIn(key, vars(action))

    def test_identity_reader_keeps_two_calibrations(self):
        reader = formation.FormationIdentityReader
        with patch.object(reader, "__init__", return_value=None):
            calibrations = [formation.FormationCalibration(calibration_id=str(i)) for i in range(5)]
            refs = [weakref.ref(reader.acquire(["fixtures"], c)) for c in calibrations]
            gc.collect()
            self.assertTrue(all(ref() is None for ref in refs[:-2]))
            for ref, calibration in zip(refs[-2:], calibrations[-2:]):
                self.assertIs(ref(), reader.acquire(["fixtures"], calibration))

    def test_scale_change_drops_old_templates(self):
        reader = formation.FormationIdentityReader.__new__(formation.FormationIdentityReader)
        reader.sx = reader.sy = 1.0
        marker = np.random.default_rng(42).integers(0, 256, (16, 16, 3), np.uint8)
        reader.config_marker = marker
        reader.start_markers = [marker]
        reader.calibration = formation.FormationCalibration()
        reader._empty_slot_reason = Mock(return_value="empty")
        full = np.zeros((720, 1280, 3), np.uint8)
        full[16:32, 16:32] = marker
        reader.read_frame(full)
        old_keys = set(reader._tpl_scale_cache)
        self.assertTrue(old_keys)
        reader.read_frame(cv2.resize(full, (640, 360)))
        self.assertIn((id(marker), 8, 8), reader._tpl_scale_cache)
        self.assertTrue(old_keys.isdisjoint(reader._tpl_scale_cache))
