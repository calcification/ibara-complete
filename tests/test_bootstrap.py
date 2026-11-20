#!/usr/bin/env python3
"""Test Phase 3 boot routing using a disc made entirely from homebrew data."""

import hashlib
import importlib.util
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'bootstrap', ROOT / 'research/phase03/ibara_complete_bootstrap.py'
)
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def make_source(path):
    sector = bootstrap.SECTOR
    root_lba, config_lba, boot_lba = 24, 25, 26
    probe_lba, new_config_lba, next_file_lba = 28, 29, 31
    config = b'BOOT2 = cdrom0:\\SLPM_663.01;1\r\nVER = 1.00\r\nVMODE = NTSC\r\n'
    baseline = bytearray(bootstrap.build_probe_elf())
    # Give the homebrew baseline a green signature instead of magenta.
    struct.pack_into('<2I', baseline, 0x8C, 0x3C090000, 0x3529FF00)
    files = {
        b'SYSTEM.CNF;1': (config_lba, config),
        b'SLPM_663.01;1': (boot_lba, baseline),
    }
    for index in range(6):
        files[f'PAD{index}.DAT;1'.encode('ascii')] = (next_file_lba + index, b'\0')

    file_records = b''.join(
        bootstrap.make_file_record(name, lba, len(data))
        for name, (lba, data) in files.items()
    )
    root_size = 2 * 34 + len(file_records)
    directory_records = []
    for name in (b'\0', b'\1'):
        record = bytearray(bootstrap.make_file_record(name, root_lba, root_size))
        record[25] = 2
        directory_records.append(record)

    image = bytearray(40 * sector)
    pvd = memoryview(image)[16 * sector:17 * sector]
    pvd[:7] = b'\x01CD001\x01'
    pvd[8:72] = b'PLAYSTATION'.ljust(32) + b'HOMEBREW'.ljust(32)
    pvd[80:88] = bootstrap.pair32(len(image) // sector)
    pvd[120:124] = bootstrap.pair16(1)
    pvd[124:128] = bootstrap.pair16(1)
    pvd[128:132] = bootstrap.pair16(sector)
    pvd[132:140] = bootstrap.pair32(10)
    struct.pack_into('<I', pvd, 140, 18)
    struct.pack_into('>I', pvd, 148, 19)
    pvd[156:190] = directory_records[0]
    pvd[881] = 1
    image[17 * sector:17 * sector + 7] = b'\xffCD001\x01'
    struct.pack_into('<BBIH2x', image, 18 * sector, 1, 0, root_lba, 1)
    struct.pack_into('>BBIH2x', image, 19 * sector, 1, 0, root_lba, 1)
    image[root_lba * sector:root_lba * sector + root_size] = b''.join(directory_records) + file_records
    for lba, data in files.values():
        image[lba * sector:lba * sector + len(data)] = data

    path.write_bytes(image)
    return {
        'EXPECTED_ISO_LEN': len(image),
        'EXPECTED_SHA256': hashlib.sha256(image).hexdigest(),
        'EXPECTED_CRC': {'SLPM_663.01;1': (boot_lba, len(baseline), zlib.crc32(baseline))},
        'ORIGINAL_ROOT_LBA': root_lba,
        'ORIGINAL_ROOT_LEN': root_size,
        'NEW_FILE_LBA': probe_lba,
        'NEW_CNF_LBA': new_config_lba,
        'NEXT_ORIGINAL_FILE_LBA': next_file_lba,
    }


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / 'source.iso'
        self.output = self.source.with_name('output.iso')
        source_constants = patch.multiple(bootstrap, **make_source(self.source))
        source_constants.start()
        self.addCleanup(source_constants.stop)

    def test_probe_fixture_matches_builder_and_debugger_loop(self):
        elf = (ROOT / 'tests/fixtures/KURO_PROBE.ELF').read_bytes()
        self.assertEqual(elf, bootstrap.build_probe_elf())
        entry, header_offset = struct.unpack_from('<II', elf, 24)
        load_type, load_offset, load_address = struct.unpack_from('<III', elf, header_offset)
        self.assertEqual((load_type, entry, load_address), (1, 0x00100000, 0x00100000))
        loop_offset = 0x00100018 - load_address + load_offset
        self.assertEqual(struct.unpack_from('<II', elf, loop_offset), (0x1000FFFF, 0))

    def test_both_modes_route_to_the_expected_elf(self):
        expected_paths = {'inject': b'SLPM_663.01;1', 'probe': b'KURO.ELF;1'}
        for mode, expected_path in expected_paths.items():
            with self.subTest(mode=mode):
                output = self.output.with_name(f'{mode}.iso')
                bootstrap.inject(self.source, output, mode)
                image = output.read_bytes()
                sector = bootstrap.SECTOR
                offset = bootstrap.ORIGINAL_ROOT_LBA * sector
                root_size = struct.unpack_from('<I', image, 16 * sector + 166)[0]
                root_end = offset + root_size
                entries = {}
                while offset < root_end:
                    record = bootstrap.parse_record(image, offset)
                    start = record['lba'] * sector
                    entries[record['name']] = image[start:start + record['size']]
                    offset += record['record_bytes']
                self.assertEqual(entries[b'KURO.ELF;1'], bootstrap.build_probe_elf())
                self.assertIn(b'BOOT2 = cdrom0:\\' + expected_path + b'\r\n', entries[b'SYSTEM.CNF;1'])
                self.assertEqual(bootstrap.digest_file(self.source), bootstrap.EXPECTED_SHA256)

    def test_competing_output_survives_failed_exclusive_create(self):
        original_open = Path.open
        marker = b'output written by a competing process'

        def open_after_competitor_creates_output(path, mode='r', *args, **kwargs):
            if path == self.output and mode == 'xb':
                with original_open(path, 'xb') as competitor:
                    competitor.write(marker)
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', open_after_competitor_creates_output):
            with self.assertRaises(FileExistsError):
                bootstrap.inject(self.source, self.output, 'probe')
        self.assertEqual(self.output.read_bytes(), marker)


if __name__ == '__main__':
    unittest.main()
