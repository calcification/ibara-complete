import json
from pathlib import Path
import struct
import tempfile
import unittest

import replay


SCENARIOS = Path(__file__).parent / 'scenarios'


class ReplayTests(unittest.TestCase):
    def test_all_scenarios_have_300_frames(self):
        for path in SCENARIOS.glob('*.json'):
            with self.subTest(path=path):
                _, masks, _ = replay.load_plan(path)
                self.assertEqual(len(masks), 300)

    def test_native_movie_offsets_buttons_and_companion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'start.p2s'
            movie = root / 'test.p2m2'
            state.write_bytes(b'local checkpoint')
            plan = [20, 48, 0, 1024]
            replay.write_movie(movie, plan, replay.DEFAULT_PAD, state, 'PCSX2-v2.8.2', 'Replay probe', 1, 2)
            self.assertEqual((root / 'test.p2m2_SaveState.p2s').read_bytes(), state.read_bytes())
            raw = movie.read_bytes()
            self.assertEqual(len(raw), 570 + 36 * 7)
            pad = raw[606:624]
            self.assertEqual((pad[0], pad[1], pad[7], pad[12]), (0x7F, 0xBF, 255, 255))
            self.assertEqual(list(replay.read_movie(movie, replay.DEFAULT_PAD)), [0, *plan, 0, 0])
            movie.write_bytes(raw[:-1])
            with self.assertRaisesRegex(ValueError, 'recording length'):
                list(replay.read_movie(movie, replay.DEFAULT_PAD))

    def test_rejects_invalid_or_unmapped_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / 'scenario.json'
            plan.write_text(json.dumps(dict(version=1, name='bad', anchor='stage1', segments=[[1, ['up', 'down']]])))
            with self.assertRaisesRegex(ValueError, 'opposing'):
                replay.load_plan(plan)
        with self.assertRaisesRegex(ValueError, 'no PCSX2 controller mapping'):
            replay.pad_frame(1 << replay.CONTROLS.index('coin'), replay.DEFAULT_PAD)

    def test_first_difference_keeps_input_and_gameplay_separate(self):
        plan = [0, 16, 32]
        expected = [{'observed_input': mask, 'score': i} for i, mask in enumerate(plan)]
        for actual, result, frame in [
            (expected, 'match', None),
            ([expected[0], expected[1], {'observed_input': 0, 'score': 2}], 'input_desync', 2),
            ([expected[0], {'observed_input': 16, 'score': 99}, expected[2]], 'gameplay_difference', 1),
            ([{'score': 0}, {'observed_input': 16, 'score': 99}, expected[2]], 'unclassified', 1),
        ]:
            with self.subTest(result=result):
                report = replay.compare(plan, expected, actual, ['score'])
                self.assertEqual((report['classification'], report['first_divergent_frame']), (result, frame))

    def test_context_must_match_for_repeat(self):
        scenario, _, digest = replay.load_plan(SCENARIOS / 'movement.json')
        settings = {'stage': 1}
        context = dict(emulator='example', version='1', build='rom', checkpoint='start',
                       anchor=scenario['anchor'], settings=settings, rng={'policy': 'from checkpoint'},
                       sampling='post_update', scenario_sha256=digest)
        replay.verify_context(scenario, digest, context, context, True)
        with self.assertRaisesRegex(ValueError, 'identical context'):
            replay.verify_context(scenario, digest, context, context | {'checkpoint': 'other'}, True)
        with self.assertRaisesRegex(ValueError, r'bomb_stock \(left 1, right 0\)'):
            replay.verify_context(
                scenario, digest, context | {'settings': settings | {'bomb_stock': 1}},
                context | {'settings': settings | {'bomb_stock': 0}}, False,
            )

    def test_capture_alignment_matches_inputs_without_matching_telemetry(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / 'ram.bin'
            csv = Path(directory) / 'trace.csv'
            plan = [0, 4, 0, 16]
            inputs = [0, 0, *plan, 0, 0]
            data = struct.pack('<II', 0x46524231, len(inputs))
            data += b''.join(struct.pack('<iI', -20 + i, mask) for i, mask in enumerate(inputs))
            memory.write_bytes(data)
            fields = ['player_x', 'observed_input']
            selected = replay.probe_to_csv(memory, csv, 0, len(plan), 0, fields, alignment=((0, 7), plan))
            self.assertEqual(selected, 2)
            self.assertEqual(replay.load_csv(csv, len(plan))[1], {'player_x': -17, 'observed_input': 4})

    def test_alignment_rejects_ambiguous_or_incomplete_evidence(self):
        plan = [0, 16, 0]
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            replay.select_trace_start(plan + plan, plan, 0, 3)
        with self.assertRaisesRegex(ValueError, 'no complete'):
            replay.select_trace_start(plan[:-1], plan, 0, 3)
        with self.assertRaisesRegex(ValueError, 'control change'):
            replay.select_trace_start([0, 0, 0], [0, 0], 0, 1)

    def test_current_game_capture_has_fixed_layout_with_invulnerability(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Path(directory) / 'ram.bin'
            output = Path(directory) / 'trace.csv'
            frame = (32, -2, 80, 120, 16, 2, 1, 13, 3, 4, 2, 1, 2, 2, 0, 30)
            memory.write_bytes(struct.pack('<IIIii13I', 0x46524232, 1, *frame))
            replay.probe_to_csv(memory, output, 0, 1, 0, None)
            row, = replay.load_csv(output, 1)
            self.assertEqual(row['observed_input'], 32)
            self.assertEqual(row['player_x'], -2)
            self.assertEqual((row['player_can_be_hit'], row['invincibility_timer']), (0, 30))
            with self.assertRaisesRegex(ValueError, 'fixed game trace layout'):
                replay.probe_to_csv(memory, output, 0, 1, 0, ['observed_input'])


if __name__ == '__main__':
    unittest.main()
