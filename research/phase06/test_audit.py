import hashlib
import os
import pathlib
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import audit_arrange_dispatch as audit

class TestVerifiedAddresses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the supplied original ELF, not a copy shipped in this research package.
        cls.path = pathlib.Path(os.environ.get('IBARA_ORIGINAL_ELF', 'SLPM_663.01'))
        if not cls.path.exists():
            raise unittest.SkipTest('Provide the original ELF via IBARA_ORIGINAL_ELF to run binary-dependent tests')
        cls.elf = audit.load_elf(cls.path)
    def test_sha256(self):
        self.assertEqual(hashlib.sha256(self.elf).hexdigest(),audit.EXPECTED_SHA256)
    def test_known_anchor_words(self):
        for _,(va,expected) in audit.CHECKS.items():
            self.assertEqual(audit.word(self.elf,va),expected)
    def test_state_handler_table(self):
        expected=[0x139B20]+[0x139850]*9+[0x139B20]*6+[0x139050]*16+[0x138F60]
        self.assertEqual([audit.word(self.elf,audit.TABLE_ADDRESS+4*i) for i in range(33)],expected)
    def test_detects_mutation(self):
        b=bytearray(self.elf)
        va=0x1398E4; off=va-audit.LOAD_ADDRESS+audit.ELF_OFFSET
        b[off]^=1
        self.assertNotEqual(audit.word(b,va),audit.CHECKS['input_bit_0x40'][1])
        self.assertNotEqual(hashlib.sha256(b).hexdigest(),audit.EXPECTED_SHA256)
    def test_truncated_input(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'short.bin';p.write_bytes(b'\x7fELF')
            with self.assertRaises(ValueError):audit.load_elf(p)
if __name__=='__main__':
    unittest.main()
