import unittest

from src.core.normalize import normalize_summary


class TestNormalize(unittest.TestCase):
    def test_normalize_summary(self):
        raw = {
            "id": "abc",
            "duration": "120",
            "map_name": "Arena",
            "players": [
                {"player_name": "P1", "civilization": "Teutons", "feudal_age": 500},
                {"player_name": "P2", "civilization": "Britons", "castle_age": 900},
            ],
        }

        summary = normalize_summary(raw)

        self.assertEqual(summary.match_id, "abc")
        self.assertEqual(summary.duration_sec, 120)
        self.assertEqual(summary.map_name, "Arena")
        self.assertEqual(summary.players[0].name, "P1")
        self.assertEqual(summary.milestones["P1"]["feudal"], 500)
        self.assertEqual(summary.milestones["P2"]["castle"], 900)


if __name__ == "__main__":
    unittest.main()
