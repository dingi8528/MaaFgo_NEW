"""主战斗界面稳定等待的离线回归测试。"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT / "agent" / "custom")]

from battle.core.enums import Scene
from battle.runtime.runtime import AutoBattleRuntime


class BattleMainSettleTest(unittest.TestCase):
    def _runtime(self, frames, events):
        runtime = AutoBattleRuntime.__new__(AutoBattleRuntime)
        runtime.ctx = object()
        runtime.decider = SimpleNamespace(plan=None)

        class Controller:
            def post_screencap(self):
                events.append("screenshot")
                return self

            def wait(self):
                return self

            def get(self):
                return frames.pop(0)

        runtime.controller = Controller()
        return runtime

    def test_main_battle_waits_then_recaptures_before_perception(self):
        first, settled = object(), object()
        events = []
        runtime = self._runtime([first, settled], events)
        state = SimpleNamespace(scene=Scene.MAIN_BATTLE)

        def detect(_context, image):
            self.assertIs(image, first)
            events.append("detect")
            return Scene.MAIN_BATTLE

        def sleep(seconds):
            self.assertEqual(seconds, 1.0)
            events.append("sleep")

        def build(_context, image):
            self.assertIs(image, settled)
            events.append("build")
            return state

        with patch("battle.runtime.runtime.perception.detect_scene", side_effect=detect), \
                patch("battle.runtime.runtime.perception.build", side_effect=build), \
                patch("battle.runtime.runtime.time.sleep", side_effect=sleep):
            self.assertIs(runtime._observe(settle_main=True), state)

        self.assertEqual(events, ["screenshot", "detect", "sleep", "screenshot", "build"])

    def test_other_scene_does_not_wait_or_recapture(self):
        frame = object()
        events = []
        runtime = self._runtime([frame], events)
        state = SimpleNamespace(scene=Scene.VICTORY)

        with patch("battle.runtime.runtime.perception.detect_scene", return_value=Scene.VICTORY), \
                patch("battle.runtime.runtime.perception.build", return_value=state) as build, \
                patch("battle.runtime.runtime.time.sleep") as sleep:
            self.assertIs(runtime._observe(settle_main=True), state)

        sleep.assert_not_called()
        build.assert_called_once_with(runtime.ctx, frame)
        self.assertEqual(events, ["screenshot"])


if __name__ == "__main__":
    unittest.main()
