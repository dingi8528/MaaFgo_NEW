import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent" / "custom"))

from agent.chaldea import _build_cache_name
from agent.chaldea.chaldea_client import _normalize_team, select_best_team


class ChaldeaClientTests(unittest.TestCase):
    def test_normalize_new_api_team(self):
        team = _normalize_team({
            "id": 123,
            "data": "Gcompressed",
            "quest_id": 93000002,
            "up": 9,
            "down": 2,
        })

        self.assertEqual(team["content"], "Gcompressed")
        self.assertEqual(team["questId"], 93000002)
        self.assertEqual(team["votes"], {"up": 9, "down": 2})

    def test_normalize_does_not_overwrite_legacy_fields(self):
        team = _normalize_team({
            "content": "Hold",
            "data": "Gnew",
            "questId": 1,
            "quest_id": 2,
            "votes": {"up": 7, "down": 1},
            "up": 99,
        })

        self.assertEqual(team["content"], "Hold")
        self.assertEqual(team["questId"], 1)
        self.assertEqual(team["votes"], {"up": 7, "down": 1})

    def test_select_best_team_supports_new_api_vote_fields(self):
        best = select_best_team([
            {"id": 1, "up": 12, "down": 10},
            {"id": 2, "up": 8, "down": 1},
        ])

        self.assertEqual(best["id"], 2)

    def test_normalize_and_select_support_plural_vote_fields(self):
        teams = [
            _normalize_team({"id": 1, "upvotes": 12, "downvotes": 10}),
            _normalize_team({"id": 2, "upvotes": 8, "downvotes": 1}),
        ]

        self.assertEqual(teams[0]["votes"], {"up": 12, "down": 10})
        self.assertEqual(teams[1]["votes"], {"up": 8, "down": 1})
        self.assertEqual(select_best_team(teams)["id"], 2)

    def test_cache_name_ignores_null_public_team_slots(self):
        name = _build_cache_name(
            {"team": {"onFieldSvts": [{"svtId": 700500}, None, None]}},
            93000002,
            41708,
        )

        self.assertTrue(name.endswith("_41708_93000002"))


if __name__ == "__main__":
    unittest.main()
