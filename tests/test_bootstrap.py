#!/usr/bin/env python3
"""Test Phase 3 boot routing using a disc made entirely from homebrew data."""

import hashlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research/phase04'))
import build_menu_probe as menu
import build_ee_hooks as hooks

bootstrap = menu.disc


class CompanionFilesTests(unittest.TestCase):
    def test_directory_records_and_contents(self):
        sector = menu.disc.SECTOR
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'file=pattern.dat'
            contents = bytes(range(256)) * 9
            source.write_bytes(contents)
            empty = Path(directory) / 'empty'
            empty.touch()
            with patch.object(menu.disc, 'NEW_FILE_LBA', 1):
                entries, companions, start_lba, end_lba = menu.companion_layout(
                    [f'pattern.dat={source}', f'empty={empty}'], [], sector + 1,
                )
            offset = 0
            for name, lba, size in [
                (menu.disc.PROBE_FILENAME, 1, sector + 1),
                (b'PATTERN.DAT;1', 3, len(contents)),
                (b'EMPTY;1', 5, 0),
            ]:
                record = menu.disc.parse_record(entries, offset)
                self.assertEqual((record['name'], record['lba'], record['size']), (name, lba, size))
                offset += record['record_bytes']
            self.assertEqual(offset, len(entries))
            self.assertEqual(start_lba, 1)
            self.assertEqual(end_lba, 6)
            with tempfile.TemporaryFile() as target:
                target.truncate(end_lba * sector)
                for path, location, size in companions:
                    menu.write_companion(target, path, location, size, 1024)
                target.seek(3 * sector)
                self.assertEqual(target.read(), contents + bytes(3 * sector - len(contents)))

    def test_near_assets_extents_are_packed_against_original_files(self):
        sector = menu.disc.SECTOR
        with tempfile.TemporaryDirectory() as directory:
            companion = Path(directory) / 'file.dat'
            companion.write_bytes(bytes(sector + 1))
            with patch.object(menu.disc, 'NEW_FILE_LBA', 1), patch.object(
                menu.disc, 'NEXT_ORIGINAL_FILE_LBA', 12,
            ):
                entries, companions, start_lba, end_lba = menu.companion_layout(
                    [f'DATA.DAT={companion}'], [], sector, near_assets=True, boot_sectors=2,
                )
            self.assertEqual((start_lba, end_lba), (7, 10))
            elf = menu.disc.parse_record(entries, 0)
            data = menu.disc.parse_record(entries, elf['record_bytes'])
            self.assertEqual((elf['lba'], data['lba']), (7, 8))
            self.assertEqual(companions, [(companion, 8 * sector, sector + 1)])

    def test_oversized_payload_cannot_shift_before_reserved_extent(self):
        with patch.object(menu.disc, 'NEXT_ORIGINAL_FILE_LBA', menu.disc.NEW_FILE_LBA + 1):
            with self.assertRaisesRegex(ValueError, 'reserved disc extent'):
                menu.companion_layout([], [], menu.disc.SECTOR + 1, near_assets=True)

    def test_rejects_unsafe_disc_layouts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'fixture.bin'
            source.touch()
            records = [{'name': b'SYSTEM.CNF;1'}, {'name': b'IOP'}]
            cases = [
                ([f'../A.DAT={source}'], 'ISO 8.3'),
                ([f'kuro.elf={source}'], 'already in use'),
                ([f'system.cnf={source}'], 'already in use'),
                ([f'iop={source}'], 'already in use'),
                ([f'A.DAT={source}', f'a.dat={source}'], 'already in use'),
                ([f'F{i:07}.DAT={source}' for i in range(40)], 'root directory space'),
            ]
            for files, message in cases:
                with self.subTest(files=files), self.assertRaisesRegex(ValueError, message):
                    menu.companion_layout(files, records, 160)
            with patch.object(menu.disc, 'NEXT_ORIGINAL_FILE_LBA', menu.disc.NEW_FILE_LBA + 1):
                with self.assertRaisesRegex(ValueError, 'reserved disc extent'):
                    menu.companion_layout([f'A.DAT={source}'], records, 160)


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

    def test_launcher_rejects_malformed_payload_before_creating_output(self):
        payload = self.source.with_suffix('.elf')
        for field, width, value, error in [
            (40, '<H', 0, 'Invalid MIPS executable header'),
            (52 + 16, '<I', 4096, 'load segment exceeds'),
            (52 + 16, '<I', 0, 'entry point must be inside'),
        ]:
            with self.subTest(field=field, value=value):
                probe = bytearray(bootstrap.build_probe_elf())
                struct.pack_into(width, probe, field, value)
                payload.write_bytes(probe)
                with self.assertRaisesRegex(ValueError, error):
                    menu.build(self.source, self.output, payload)
                self.assertFalse(self.output.exists())

    def test_launcher_rejects_oversized_companion_before_creating_output(self):
        companion = self.source.with_suffix('.dat')
        free_sectors = bootstrap.NEXT_ORIGINAL_FILE_LBA - bootstrap.NEW_FILE_LBA
        with companion.open('wb') as file:
            file.truncate(free_sectors * bootstrap.SECTOR)
        with (patch.object(menu, 'menu_elf', return_value=bootstrap.build_probe_elf()),
              self.assertRaisesRegex(ValueError, 'reserved disc extent')):
            menu.build(self.source, self.output, disc_files=[f'DATA.DAT={companion}'])
        self.assertFalse(self.output.exists())

    def test_launcher_auto_installs_frontend_hook_when_called_directly(self):
        executable = bootstrap.build_probe_elf()
        boot = {'lba': bootstrap.EXPECTED_CRC['SLPM_663.01;1'][0], 'bytes': len(executable)}
        with (patch.object(menu.retail, 'load_input', return_value=(executable, [], boot)),
              patch.object(menu, 'label_writes', return_value=[]),
              patch.object(menu, 'menu_elf', return_value=executable),
              patch.object(hooks, 'standalone_video_hook') as select):
            select.return_value.return_value = executable
            menu.build(self.source, self.output, video_profile='auto')
        select.assert_called_once_with()
        select.return_value.assert_called_once_with(executable)
        self.assertTrue(self.output.is_file())

    def test_launcher_cleans_up_interrupted_build(self):
        companion = self.source.with_suffix('.dat')
        companion.write_bytes(b'homebrew companion')
        executable = bootstrap.build_probe_elf()
        boot_lba = bootstrap.EXPECTED_CRC['SLPM_663.01;1'][0]

        def interrupt(target, *args):
            self.assertGreater(target.tell(), 0)
            raise KeyboardInterrupt

        boot = {'lba': boot_lba, 'bytes': len(executable)}
        with (patch.object(menu.retail, 'load_input', return_value=(executable, [], boot)),
              patch.object(menu, 'label_writes', return_value=[]),
              patch.object(menu, 'menu_elf', return_value=executable),
              patch.object(menu, 'write_companion', side_effect=interrupt)):
            with self.assertRaises(KeyboardInterrupt):
                menu.build(self.source, self.output, disc_files=[f'DATA.DAT={companion}'])
        self.assertFalse(self.output.exists())
        self.assertEqual(bootstrap.digest_file(self.source), bootstrap.EXPECTED_SHA256)


if __name__ == '__main__':
    unittest.main()
