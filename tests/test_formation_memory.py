"""编队动作复用时，只保留当前帧和近期校准所需的图像。"""
import gc
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

import cv2
import numpy as np

from formation_test_support import formation


IMAGE_FIELDS = (
    "_roi_crop_cache", "_tpl_scale_cache", "local_templates", "support_templates",
    "identity_templates", "equip_team_templates", "equip_list_templates", "equip_database",
    "support_marker", "edit_marker", "config_marker", "select_page_markers",
    "formation_confirm_marker", "equip_confirm_marker", "grand_equip_popup_marker",
)


class FormationMemoryTests(unittest.TestCase):
    @patch.object(formation.time, "sleep")
    def test_shot_keeps_only_current_frame_crops(self, sleep):
        action = formation.AutoFormationFromChaldea()
        action.sx = action.sy = 1.0
        action.controller = SimpleNamespace(post_screencap=lambda: None)
        template = np.ones((4, 4, 3), np.uint8)
        frames = []
        for i in range(50):
            action.controller.cached_image = np.full((32, 32, 3), i, np.uint8)
            frame = action._shot()
            frames.append(weakref.ref(frame))
            action._match_template(frame, template, (0, 0, 16, 16))
        gc.collect()
        self.assertEqual(len(action._roi_crop_cache), 1)
        self.assertTrue(all(ref() is None for ref in frames[:-1]))

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
