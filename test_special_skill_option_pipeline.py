from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parent
PIPELINE_PATH = ROOT / "assets/resource/base/pipeline/自动战斗_特殊技能.json"
IMAGE_ROOT = ROOT / "assets/resource/base/image"


class SpecialSkillOptionPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))

    def test_all_new_select_add_info_options_are_declared(self) -> None:
        expected_groups = {
            "马嘶": ["无敌选择", "毅力选择"],
            "梵高矿工": ["Quick选择", "Arts选择", "Buster选择"],
            "莉莉丝": ["不赋予选择", "赋予选择"],
            "普雷拉蒂": ["不换形态选择", "换形态选择"],
            "夏洛特": ["Arts选择", "暴击威力选择", "宝具威力选择"],
            "芙萝拉": ["通常状态选择", "冥界之花园状态选择"],
            "安哥拉曼纽": ["无毅力选择", "50%毅力选择", "1HP毅力选择"],
            "但丁": ["天国Arts选择", "地狱Buster选择"],
        }
        for servant, suffixes in expected_groups.items():
            matches = [name for name in self.pipeline if f"战斗_{servant}" in name]
            for suffix in suffixes:
                self.assertTrue(
                    any(name.endswith(suffix) for name in matches),
                    f"missing {servant} option {suffix}",
                )

    def test_exactly_one_fixed_default_per_new_skill_is_in_root(self) -> None:
        root_next = self.pipeline["战斗_特殊技能处理"]["next"]
        defaults = [
            "战斗_马嘶1技能_无敌选择",
            "战斗_梵高矿工1技能_Arts选择",
            "战斗_莉莉丝3技能_不赋予选择",
            "战斗_普雷拉蒂1技能_不换形态选择",
            "战斗_夏洛特3技能_Arts选择",
            "战斗_芙萝拉3技能_通常状态选择",
            "战斗_安哥拉曼纽3技能_50%毅力选择",
            "战斗_但丁2技能_天国Arts选择",
        ]
        for node in defaults:
            self.assertEqual(root_next.count(node), 1)
        self.assertLess(
            max(root_next.index(node) for node in defaults),
            root_next.index("战斗_技能目标子屏"),
        )
        self.assertLess(
            root_next.index("战斗_技能目标子屏"),
            root_next.index("战斗_特殊技能_无覆盖层"),
        )

    def test_verified_jp_templates_exist(self) -> None:
        verified_nodes = [
            name
            for name in self.pipeline
            if any(
                key in name
                for key in (
                    "战斗_马嘶1技能", "战斗_梵高矿工1技能",
                    "战斗_莉莉丝3技能", "战斗_普雷拉蒂1技能",
                    "战斗_芙萝拉3技能",
                )
            )
        ]
        self.assertEqual(len(verified_nodes), 11)
        for name in verified_nodes:
            recognition = self.pipeline[name]["recognition"]
            self.assertEqual(recognition["type"], "TemplateMatch")
            template = recognition["param"]["template"]
            path = IMAGE_ROOT / template
            self.assertTrue(path.is_file(), template)
            with path.open("rb") as stream:
                self.assertEqual(stream.read(8), b"\x89PNG\r\n\x1a\n")
                length = struct.unpack(">I", stream.read(4))[0]
                self.assertEqual(stream.read(4), b"IHDR")
                self.assertEqual(length, 13)
                width, height = struct.unpack(">II", stream.read(8))
            self.assertEqual(
                (width, height), tuple(recognition["param"]["roi"][2:]), template
            )

    def test_unverified_options_use_exact_japanese_ocr_labels(self) -> None:
        expected = {
            "战斗_夏洛特3技能_Arts选择": "Artsアップ",
            "战斗_夏洛特3技能_暴击威力选择": "クリティカル威力アップ",
            "战斗_夏洛特3技能_宝具威力选择": "宝具威力アップ",
            "战斗_安哥拉曼纽3技能_无毅力选择": "ガッツなし",
            "战斗_安哥拉曼纽3技能_50%毅力选择": "ガッツ50%回復",
            "战斗_安哥拉曼纽3技能_1HP毅力选择": "ガッツ1回復",
            "战斗_但丁2技能_天国Arts选择": "天国化(Arts強化)",
            "战斗_但丁2技能_地狱Buster选择": "地獄化(Buster強化)",
        }
        for node, label in expected.items():
            recognition = self.pipeline[node]["recognition"]
            self.assertEqual(recognition["type"], "OCR")
            self.assertIn(label, recognition["param"]["expected"])


if __name__ == "__main__":
    unittest.main()
