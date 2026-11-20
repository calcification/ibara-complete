#!/usr/bin/env python3
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_rank_scoring import (elf_bytes,analyze,find_calls,word,EXPECTED_WORDS,
                                ORIGINAL_SHA256, RANK_UP, RANK_DOWN,ELF_LOAD_OFFSET,LOAD_ADDR)

# Pass a local ELF path as the first argument, or set IBARA_ORIGINAL_ELF.
# No copyrighted game binary is bundled with this research package.
LOCAL_ELF=Path(os.environ.get('IBARA_ORIGINAL_ELF', sys.argv.pop(1) if len(sys.argv)>1 else str(Path(__file__).with_name('SLPM_663.01'))))

class OfflineAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LOCAL_ELF.is_file():
            raise FileNotFoundError(f'Provide original retail ELF: python test_audit_rank_scoring.py \"path/to/SLPM_663.01\" (missing {LOCAL_ELF})')
        cls.data=LOCAL_ELF.read_bytes()

    def test_verified_signature(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), ORIGINAL_SHA256)
        result=analyze(self.data,'elf')
        self.assertEqual(result['checks']['fingerprinted_instructions'],60)

    def test_rank_callsite_counts(self):
        calls=find_calls(self.data)
        self.assertEqual(len(calls),58)
        self.assertEqual(sum(int(x['target'],16)==RANK_UP for x in calls),2)
        self.assertEqual(sum(int(x['target'],16)==RANK_DOWN for x in calls),56)
        self.assertEqual([x['callsite'] for x in calls if int(x['target'],16)==RANK_UP],['0x0012F708','0x00139020'])

    def test_known_imm_tables(self):
        d=analyze(self.data,'elf')
        self.assertEqual(d['tables']['item_rank_delta_0x20BFD0_first_four'],[256,512,768,1024])
        self.assertEqual(d['tables']['stock_indexed_rank_relief_0x213070_eight'],[0x400000,0x200000,0x100000,0x80000,0x40000,0x20000,0x200000,0x200000])
        self.assertEqual(d['tables']['extend_threshold_candidates_0x213540_seven'][1:4],[1000000,2000000,3000000])

    def test_word_address_translation(self):
        self.assertEqual(word(self.data,0x0012F708),0x0C04A770)
        self.assertEqual(word(self.data,0x0012F70C),0x00022280)
        self.assertEqual(word(self.data,0x0013AC58),0x34639680)

    def test_elf_file_reader(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'retail.elf';p.write_bytes(self.data)
            raw,kind=elf_bytes(p)
            self.assertEqual(kind,'elf')
            self.assertEqual(raw,self.data)

    def test_corrupt_instruction_rejected(self):
        corrupted=bytearray(self.data)
        address=next(iter(EXPECTED_WORDS))
        corrupted[address-LOAD_ADDR+ELF_LOAD_OFFSET] ^= 0x01
        with self.assertRaisesRegex(ValueError,'SHA256'):
            analyze(bytes(corrupted),'elf')

    def test_wrong_format_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'wrong.iso';p.write_bytes(b'no iso here')
            with self.assertRaisesRegex(ValueError,'Not an ELF or'):
                elf_bytes(p)

    def test_do_not_write_original(self):
        before=hashlib.sha256(LOCAL_ELF.read_bytes()).hexdigest()
        analyze(self.data,'elf')
        self.assertEqual(before,hashlib.sha256(LOCAL_ELF.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main(verbosity=2)
