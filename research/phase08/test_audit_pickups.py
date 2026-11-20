#!/usr/bin/env python3
"""Read-only unit tests. Usage: python test_audit_pickups.py path/to/SLPM_663.01"""
import sys, unittest, struct
from pathlib import Path
import audit_pickups as a
SOURCE = sys.argv[1] if len(sys.argv)>1 else None

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.elf,cls.kind=a.extract_elf(Path(SOURCE))

    def test_original_sha_and_integrity(self):
        report=a.audit(self.elf)
        self.assertEqual(report['elf_sha256'],a.ELF_SHA256)
        self.assertEqual(len(report['types']),8)

    def test_corrected_memory_address(self):
        r=a.audit(self.elf)
        self.assertEqual(r['player1_score_corrected'],'0x0044C600')
        self.assertEqual(r['player2_score_corrected'],'0x0044C890')

    def test_type_3_medal_reward_ladder(self):
        self.assertEqual([x['score_points'] for x in a.audit(self.elf)['medals']],a.EXPECTED_REWARDS[3])

    def test_medal_rank_arithmetic_differences(self):
        medals=a.audit(self.elf)['medals']
        self.assertEqual(medals[0]['arcade_rank_stored_delta_down'],256)
        self.assertEqual(medals[9]['arcade_rank_stored_delta_down'],1024)
        self.assertEqual(medals[-1]['arcade_rank_stored_delta_down'],4096)
        self.assertEqual(medals[-1]['arrange_rank_stored_delta_down'],18<<17)

    def test_item_dispatch_jal(self):
        self.assertEqual(a.jal_target(a.word(self.elf,0x12a61c),0x12a61c),0x12fd00)

    def test_modified_elf_refused_by_sha(self):
        b=bytearray(self.elf)
        b[0x200] ^= 1
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            a.audit(bytes(b))

    def test_altered_medal_reward_refused_independently(self):
        b=bytearray(self.elf)
        off=a.META_PTRS[3]+4+9*16-a.LOAD+a.SEGMENT_OFFSET
        struct.pack_into('<I',b,off,999999)
        with self.assertRaisesRegex(ValueError,'medal rewards'):
            a.audit(bytes(b),verify_sha=False)

    def test_altered_dispatch_refused_independently(self):
        b=bytearray(self.elf)
        off=a.HANDLER_TABLE+3*4-a.LOAD+a.SEGMENT_OFFSET
        struct.pack_into('<I',b,off,0x123456)
        with self.assertRaisesRegex(ValueError,'Eight item dispatch'):
            a.audit(bytes(b),verify_sha=False)

    def test_nonjal_refused(self):
        with self.assertRaisesRegex(ValueError,'Not JAL'):
            a.jal_target(0x00000000,0x12a61c)

    def test_no_game_data_in_results(self):
        r=a.audit(self.elf)
        self.assertNotIn('rom',r)
        self.assertTrue(all(len(x['verified_reward_samples']) <=19 for x in r['types']))

if __name__=='__main__':
    if not SOURCE:
        raise SystemExit('Usage: python test_audit_pickups.py SLPM_663.01')
    sys.argv=[sys.argv[0]]
    unittest.main(verbosity=2)
