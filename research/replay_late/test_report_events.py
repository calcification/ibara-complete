"""Regression checks for the late replay reporter's frame and event attribution."""
import unittest

from report_events import BASE, MAX_EVENTS, ROWS, SIDE_SIZE, START, WORDS, compare_events


class LateEventTests(unittest.TestCase):
    def setUp(self):
        self.mem = bytearray(BASE + 2 * SIDE_SIZE)
        self.write_trace(0)
        self.write_trace(1)

    def write_trace(self, side, updates=None, dropped_at=None):
        updates = updates or {}
        base = BASE + side * SIDE_SIZE
        used = 0
        for i in range(ROWS):
            update = START + i
            events = updates.get(update, ())
            WORDS.pack_into(self.mem, base + i * WORDS.size,
                            (2 << 24) | update, used, len(events), int(update == dropped_at))
            for event in events:
                WORDS.pack_into(self.mem, base + (ROWS + used) * WORDS.size, *event)
                used += 1

    def test_identifies_one_update_retail_graze_delay(self):
        rng = (1, 0x123450, 18, 0x12345678)
        graze = (5, 0x12A92C, 7 << 8, 110)
        self.write_trace(0, {1070: (rng, graze)})
        self.write_trace(1, {1070: (rng,), 1071: (graze,)})
        report = compare_events(self.mem)
        first = report["first_event_difference"]
        self.assertEqual((first["update"], first["ordinal"]), (1070, 1))
        self.assertEqual(first["record"]["event"], "retail_graze")
        self.assertEqual(first["record"]["slot"], 7)
        self.assertIsNone(first["playback"])
        self.assertEqual(set(report["first_by_kind"]), {"retail_graze"})
        self.assertEqual(report["updates_with_event_differences"], 2)

    def test_accepts_a_busy_update_with_195_events(self):
        updates = {1038: [(1, 0x123450, 18, 0x12345678)] * 195}
        for side in range(2):
            self.write_trace(side, updates)
        report = compare_events(self.mem)
        self.assertEqual(report["counts"][0]["rng"], 195)
        self.assertIsNone(report["first_event_difference"])

    def test_rejects_dropped_events(self):
        self.write_trace(1, {1078: [(1, 0, 0, 0)] * MAX_EVENTS}, dropped_at=1078)
        with self.assertRaisesRegex(ValueError, "truncated trace at update 1078"):
            compare_events(self.mem)


if __name__ == "__main__":
    unittest.main()
