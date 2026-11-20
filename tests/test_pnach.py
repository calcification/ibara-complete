#!/usr/bin/env python3
"""Offline regression tests for the PCSX2-first patch profile suite."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_pnach',ROOT/'scripts/build_pnach.py')
pnach=importlib.util.module_from_spec(spec)
spec.loader.exec_module(pnach)

class PatchTests(unittest.TestCase):
    def test_correct_crc_and_name(self):
        self.assertEqual(pnach.CRC, '420C7FAB')
        self.assertEqual(pnach.NAME, 'SLPM-66301_420C7FAB.pnach')
    def test_exact_six_groups(self):
        self.assertEqual(set(pnach.TESTS), {'240p_core','240p_halfpixel','score_marker','rank_easy','rank_hard','medal_first_10000'})
    def test_video_patch_count_and_addresses(self):
        self.assertEqual(len(pnach.VIDEO_EDITS),14)
        self.assertEqual(len(pnach.HALFPIXEL_EDITS),4)
        self.assertEqual([p[0] for p in pnach.VIDEO_EDITS],[int(x,16) for x in ['001AD250','001AF11C','001DD1C0','001DD1C8','001DD1D0','001DD1D8','001DD200','001DD208','001DD210','001DD218','001DD240','001DD248','001DD250','001DD258']])
    def test_generator_all_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            pnach.write_files(folder)
            combo=(folder/pnach.NAME).read_text()
            self.assertEqual(pnach.check_pnach(combo),{'groups':6,'writes':36})
            for key in pnach.TESTS:
                code=(folder/'profiles'/key/pnach.NAME).read_text()
                self.assertEqual(pnach.check_pnach(code)['groups'],1)
            self.assertEqual(pnach.check_pnach((folder/'profiles/baseline'/pnach.NAME).read_text()),{'groups':0,'writes':0})
    def test_bad_line_rejected(self):
        bad=pnach.HEADER+'\n[X]\npatch=2,EE,00100001,word,12345678\n'
        with self.assertRaises(AssertionError):pnach.check_pnach(bad)
    def test_duplicate_write_rejected(self):
        t=pnach.HEADER+'\n[Duplicate]\npatch=2,EE,00100000,word,00000000\npatch=2,EE,00100000,word,00000001\n'
        with self.assertRaises(AssertionError):pnach.check_pnach(t)
    def test_legacy_checksum_and_crc32_distinct(self):
        self.assertNotEqual(int(pnach.CRC,16),0xF9085060)
    def test_first_medal_original_100(self):
        self.assertEqual(pnach.MEDAL_REWARD,(0x0020B104,0x00000064,0x00002710))
    def test_runtime_player_score_address_corrected(self):
        self.assertEqual(pnach.TESTS['score_marker']['edits'][0][0],0x0044C600)
    def test_invalid_elf_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fake.elf'
            path.write_bytes(b'\x7fELF'+b'\0'*256)
            with self.assertRaises(ValueError):pnach.load_elf(path)
    def test_real_elf_if_available(self):
        src=sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('-') else None
        if src: self.assertEqual(pnach.xor_elf_crc(pnach.load_elf(Path(src))),int(pnach.CRC,16))

if __name__=='__main__':
    # optional user ELF/ISO is read directly without ever copying or writing it
    src=sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith('-') else None
    if src:sys.argv=sys.argv[:1]
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PatchTests)
    res=unittest.TextTestRunner(verbosity=2).run(suite)
    if src:
        try:
            pnach.load_elf(Path(src));print('PASS exact original ISO/ELF preimage')
        except Exception as e:
            print('FAIL original ISO/ELF preimage:',e,file=sys.stderr);res.failures.append((None,str(e)))
    sys.exit(0 if res.wasSuccessful() else 1)
