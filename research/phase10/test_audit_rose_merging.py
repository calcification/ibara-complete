#!/usr/bin/env python3
"""Unittest suite for the static Ibara Complete Phase 10 audit.
Uses an original ELF path from the command line or IBARA_ORIGINAL_ELF.
Example: python -m unittest -v test_audit_rose_merging.py
"""
import os
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import audit_rose_merging as a

SOURCE=Path(os.environ.get('IBARA_ORIGINAL_ELF', str(Path(__file__).with_name('SLPM_663.01'))))

class Phase10(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.elf,cls.source=a.extract_elf(SOURCE)

    def test_complete_exact_original_audit(self):
        r=a.audit_elf(self.elf)
        self.assertEqual(r['instruction_fingerprints_checked'],82)
        self.assertEqual(r['jal_edges_checked'],4)
        self.assertEqual(r['candidate_count'],256)
        self.assertEqual(r['candidate_stride_bytes'],88)
        self.assertEqual(r['type_update_targets'][7],'0x00132BC0')

    def test_each_type_update_handler(self):
        for i,v in enumerate(a.EXPECTED_UPDATE_TABLE):
            self.assertEqual(a.word(self.elf,a.UPDATE_TABLE_ADDR+i*4),v)

    def test_original_call_edges(self):
        for origin,target in a.JAL_EDGES.items():
            self.assertEqual(a.jal_target(a.word(self.elf,origin),origin),target)

    def test_original_branch_exit_and_loop(self):
        for origin,target in [(0x00132DC8,0x00132E60),(0x0012EB78,0x0012EBD0),(0x0012EB98,0x0012EA70)]:
            self.assertEqual(a.branch_target(a.word(self.elf,origin),origin),target)

    def test_rose_merge_raw_points(self):
        out=a.hypothetical_merge(left_level=0,left_factor=100,right_level=0,right_factor=50)
        self.assertTrue(out['merged'])
        self.assertEqual((out['resulting_level'],out['resulting_factor']),(1,150))
        self.assertEqual(a.rose_points(0,100)+a.rose_points(0,50),4500)
        self.assertEqual(a.rose_points(1,150),6000)

    def test_factor_does_not_reclamp_to_300(self):
        out=a.hypothetical_merge(left_level=0,left_factor=300,right_level=0,right_factor=300)
        self.assertEqual(out['resulting_factor'],600)
        self.assertEqual(a.rose_points(out['resulting_level'],out['resulting_factor']),24000)

    def test_level_gate_at_three(self):
        a1=a.hypothetical_merge(left_level=2,left_factor=100,right_level=2,right_factor=40)
        self.assertTrue(a1['merged'])
        self.assertEqual(a1['resulting_level'],3)
        a2=a.hypothetical_merge(left_level=3,left_factor=100,right_level=3,right_factor=40)
        self.assertFalse(a2['merged'])

    def test_type_or_level_mismatch(self):
        for kw in [{'same_type':False},{'right_level':1},{'both_active':False},{'overlap':False}]:
            opts={'left_level':0,'right_level':0,'left_factor':100,'right_factor':50}
            opts.update(kw)
            self.assertFalse(a.hypothetical_merge(**opts)['merged'])

    def test_ee_unsigned_addition_wrap(self):
        r=a.hypothetical_merge(left_level=0,left_factor=0xffffffff,right_level=0,right_factor=2)
        self.assertEqual(r['resulting_factor'],1)
        self.assertEqual(a.rose_points(1,1),40)

    def test_invalid_range(self):
        with self.assertRaises(ValueError):a.rose_points(0,-1)
        with self.assertRaises(ValueError):a.hypothetical_merge(left_level=-1,right_level=0,left_factor=0,right_factor=0)

    def test_detect_mutated_opcode_without_hash_check(self):
        modified=bytearray(self.elf)
        addr=0x0012EB74
        off=a.EE_FILE_BASE+addr-a.EE_VADDR_BASE
        modified[off]^=1
        with self.assertRaisesRegex(ValueError,'opcode mismatch'):
            a.audit_elf(bytes(modified),verify_sha=False)

    def test_detect_mutated_jump_without_hash_check(self):
        modified=bytearray(self.elf)
        addr=0x00132E60
        off=a.EE_FILE_BASE+addr-a.EE_VADDR_BASE
        modified[off]^=4
        with self.assertRaisesRegex(ValueError,'opcode mismatch'):
            a.audit_elf(bytes(modified),verify_sha=False)

    def test_detect_mutated_update_table_without_hash_check(self):
        modified=bytearray(self.elf)
        addr=0x0020BF1C
        off=a.EE_FILE_BASE+addr-a.EE_VADDR_BASE
        struct.pack_into('<I',modified,off,0x1323d0)
        with self.assertRaisesRegex(ValueError,'type-update dispatch table mismatch'):
            a.audit_elf(bytes(modified),verify_sha=False)

    def test_invalid_elf_sha_revision(self):
        modified=bytearray(self.elf)
        modified[100]^=1
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            a.audit_elf(bytes(modified))

    def test_csv_and_report_export(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'anchors.csv'
            a.csv_anchors(p)
            self.assertEqual(len(p.read_text().splitlines()),len(a.ANCHORS)+1)

    def test_elf_extraction_byte_exact(self):
        e,kind=a.extract_elf(SOURCE)
        self.assertEqual(e,self.elf)
        self.assertEqual(kind,self.source)

if __name__=='__main__':unittest.main()
