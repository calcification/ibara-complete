#!/usr/bin/env python3
"""Standalone unit tests for Phase 9; pass the exact original ELF or ISO."""
import hashlib
import sys
import unittest
from pathlib import Path
from audit_cancellation import (ANCHORS,ELF_SHA256,JAL_EDGES,audit,extract_elf,
    selector_for_collision,item_from_selector,rank_factor,arrange_rose_points,get_word,jal_target)

IMAGE = None

class Phase9(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if IMAGE is None: raise ValueError("Give original SLPM_663.01 ELF or ISO")
        cls.elf, cls.kind = extract_elf(IMAGE)

    def test_sha(self):
        self.assertEqual(hashlib.sha256(self.elf).hexdigest(),ELF_SHA256)
    def test_instruction_and_edge_audit(self):
        r=audit(self.elf)
        self.assertEqual(r['verified_opcode_count'],len(ANCHORS))
        self.assertEqual(r['verified_jal_edges'],len(JAL_EDGES))
    def test_mutation_rejected_by_hash(self):
        b=bytearray(self.elf);b[0x80+(0x12F748-0x100000)]^=0x1
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            audit(bytes(b))
    def test_mutation_rejected_by_instruction_even_if_sha_not_checked(self):
        b=bytearray(self.elf);b[0x80+(0x12AE8C-0x100000)]^=0x1
        with self.assertRaisesRegex(ValueError,"opcode mismatch"):
            audit(bytes(b),False)
    def test_direct_edges(self):
        for a,t in JAL_EDGES.items():
            self.assertEqual(jal_target(get_word(self.elf,a),a),t)
    def test_arcade_selector(self):
        for t in range(12):
            for sub in range(4):
                self.assertEqual(selector_for_collision(False,t,sub),1)
                self.assertEqual(item_from_selector(1),7)
    def test_arrange_branches(self):
        for t in (1,2):
            self.assertIsNone(selector_for_collision(True,t,0))
            self.assertEqual(selector_for_collision(True,t,1),2)
            self.assertEqual(selector_for_collision(True,t,2),0)
        for t in (0,9,10):
            self.assertEqual(selector_for_collision(True,t,0),0)
        for t in (3,8,11):
            self.assertEqual(selector_for_collision(True,t,0),1)
    def test_spawn_types(self):
        self.assertEqual(item_from_selector(1),7)
        self.assertEqual(item_from_selector(2),3)
        self.assertIsNone(item_from_selector(0))
        self.assertIsNone(item_from_selector(None))
    def test_rank_factor_edges(self):
        self.assertEqual(rank_factor(0xFFFFFF),1)
        self.assertEqual(rank_factor(0xFEFFFF),1)
        self.assertEqual(rank_factor(0xFF0000),1)
        self.assertEqual(rank_factor(0),300)
        self.assertEqual(rank_factor(1),255)
        with self.assertRaises(ValueError):rank_factor(-1)
    def test_rose_score_formula(self):
        self.assertEqual(arrange_rose_points(0,1),30)
        self.assertEqual(arrange_rose_points(0,300),9000)
        self.assertEqual(arrange_rose_points(3,300),18000)
        self.assertEqual(arrange_rose_points(18,1),210)
    def test_mips_mult_encoding(self):
        mul=get_word(self.elf,0x12F748)
        self.assertEqual(((mul>>21)&31,(mul>>16)&31,(mul>>11)&31,mul&63),(2,3,7,0x18))

if __name__=='__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python test_audit_cancellation.py <SLPM_663.01 or Ibara.iso>')
    IMAGE = Path(sys.argv[1])
    sys.argv = [sys.argv[0]]
    unittest.main(verbosity=2)
