"""用正式宝具模板验证区域边界与最低等级筛选，不操作设备。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "agent/custom")]

from maa.agent.agent_server import AgentServer

with patch.object(AgentServer, "custom_action", lambda *args: lambda cls: cls):
    import support_action as support


class SupportNPMatchingTests(unittest.TestCase):
    np_dir = ROOT / "assets/resource/base/image/nplevel"
    origin = (36, 329)

    def make_frame(self, level, relative_y=148):
        # 实机贞德 Lv.4 的模板顶部位于条目原点 y+148，底部为 y+172。
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        template = support._imread(str(self.np_dir / f"{level}.png"))
        self.assertIsNotNone(template)
        x, y = self.origin[0] + 559, self.origin[1] + relative_y
        h, w = template.shape[:2]
        frame[y:y + h, x:x + w] = template
        return frame

    def matches(self, frame, expected):
        with patch.object(support.mfaalog, "info"), patch.object(support.mfaalog, "warning"):
            return support.SupportAction()._match_np(
                frame, str(self.np_dir), *self.origin, expected)

    def test_bottom_clipping_reproduces_failure_then_new_roi_matches_lv4(self):
        frame = self.make_frame(4)
        with patch.object(support, "NP_ROI", (200, 74, 580, 94)):
            self.assertFalse(self.matches(frame, 4))
        self.assertTrue(self.matches(frame, 4))

    def test_all_levels_match_near_lower_edge_and_keep_minimum_requirement(self):
        for level in range(1, 6):
            with self.subTest(level=level):
                frame = self.make_frame(level)
                self.assertTrue(self.matches(frame, level))
                self.assertFalse(self.matches(frame, level + 1))

    def test_existing_upper_position_still_matches(self):
        self.assertTrue(self.matches(self.make_frame(1, relative_y=134), 1))

    def test_next_support_entry_is_outside_roi(self):
        self.assertFalse(self.matches(self.make_frame(4, relative_y=200), 1))

    def test_unmatched_region_fails_and_no_requirement_skips_matching(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertFalse(self.matches(frame, 1))
        self.assertTrue(self.matches(frame, 0))


if __name__ == "__main__":
    unittest.main()
