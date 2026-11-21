#!/usr/bin/env python3
"""Compile deterministic replay plans and compare small emulator traces."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import struct
import zipfile
import zlib

CONTROLS = ('up', 'down', 'left', 'right', 'shot', 'bomb', 'aux', 'aux2', 'start', 'coin', 'select')
DUALSHOCK = {
    'up': (0, 0x10, 8), 'down': (0, 0x40, 9), 'left': (0, 0x80, 7), 'right': (0, 0x20, 6),
    'triangle': (1, 0x10, 10), 'circle': (1, 0x20, 11), 'cross': (1, 0x40, 12),
    'square': (1, 0x80, 13), 'l1': (1, 0x04, 14), 'r1': (1, 0x08, 15),
    'l2': (1, 0x01, 16), 'r2': (1, 0x02, 17), 'start': (0, 0x08, None),
    'select': (0, 0x01, None), 'l3': (0, 0x02, None), 'r3': (0, 0x04, None),
}
P2M_HEADER = struct.Struct('<B50s255s255sIIB')
NEUTRAL = bytes.fromhex('ff ff 7f 7f 7f 7f') + bytes(12)
DEFAULT_PAD = dict(zip(CONTROLS, ('up', 'down', 'left', 'right', 'cross', 'circle',
                                  'square', 'triangle', 'start', None, 'select'), strict=True))
SUPPORTED_METRICS = {
    'player_x', 'player_y', 'score', 'rank', 'xtc', 'hostile_bullets',
    'enemies', 'enemy_state', 'enemy_type', 'enemy_hp', 'stage', 'rng', 'observed_input',
    'bomb_stock', 'lives',
}


ENEMY_METRICS = {'enemy_type', 'enemy_state', 'enemy_hp'}


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_plan(path):
    content = path.read_bytes()
    data = json.loads(content)
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('expected a version 1 scenario')
    if not all(isinstance(data.get(key), str) and data[key] for key in ('name', 'anchor')):
        raise ValueError('scenario requires a name and anchor')
    segments = data.get('segments')
    if not isinstance(segments, list) or not segments:
        raise ValueError('scenario requires at least one segment')
    masks = []
    for segment in segments:
        if not isinstance(segment, list) or len(segment) != 2:
            raise ValueError('segments must be [frame count, held controls]')
        count, buttons = segment
        if type(count) is not int or not 1 <= count <= 100_000 or len(masks) + count > 100_000:
            raise ValueError('scenario must contain 1–100,000 frames')
        if (not isinstance(buttons, list) or any(not isinstance(b, str) or b not in CONTROLS for b in buttons)
                or len(set(buttons)) != len(buttons)):
            raise ValueError('unknown or repeated control')
        if {'up', 'down'} <= set(buttons) or {'left', 'right'} <= set(buttons):
            raise ValueError('opposing directions in one segment')
        masks.extend([sum(1 << CONTROLS.index(button) for button in buttons)] * count)
    return data, masks, hashlib.sha256(content).hexdigest()


def load_pad_map(path):
    custom = load_json(path) if path else {}
    if not isinstance(custom, dict):
        raise ValueError('PCSX2 control map must be a JSON object')
    mapping = DEFAULT_PAD | custom
    if any(key not in CONTROLS or (value is not None and value not in DUALSHOCK)
           for key, value in mapping.items()):
        raise ValueError('invalid PCSX2 control map')
    assigned = [value for value in mapping.values() if value is not None]
    if len(set(assigned)) != len(assigned):
        raise ValueError('PCSX2 buttons must map one-to-one')
    return mapping


def pad_frame(mask, mapping):
    frame = bytearray(NEUTRAL)
    for bit, control in enumerate(CONTROLS):
        if not (mask & (1 << bit)):
            continue
        button = mapping[control]
        if button is None:
            raise ValueError(f'{control} has no PCSX2 controller mapping')
        group, flag, pressure = DUALSHOCK[button]
        frame[group] &= ~flag
        if pressure is not None:
            frame[pressure] = 255
    return bytes(frame)


def write_movie(path, masks, mapping, state, emulator_version, title, lead, tail):
    def header_text(value, limit):
        raw = value.encode()
        if len(raw) >= limit:
            raise ValueError('recording header text is too long')
        return raw

    frames = [pad_frame(mask, mapping) + NEUTRAL for mask in [0] * lead + masks + [0] * tail]
    companion = Path(str(path) + '_SaveState.p2s')
    if companion.exists():
        raise FileExistsError(companion)
    header = P2M_HEADER.pack(
        1, header_text(emulator_version, 50), b'frame replay harness', header_text(title, 255),
        len(frames), 0, 1,
    )
    with path.open('xb') as movie:
        companion_created = False
        try:
            with state.open('rb') as source, companion.open('xb') as target:
                companion_created = True
                shutil.copyfileobj(source, target)
            movie.write(header + b''.join(frames))
            movie.flush()
        except BaseException:
            try:
                movie.close()
            finally:
                path.unlink(missing_ok=True)
                if companion_created:
                    companion.unlink(missing_ok=True)
            raise


def read_movie(path, mapping):
    data = path.read_bytes()
    if len(data) < P2M_HEADER.size:
        raise ValueError('truncated PCSX2 recording header')
    version, _, _, _, frames, _, from_state = P2M_HEADER.unpack_from(data)
    if version != 1 or from_state not in (0, 1) or len(data) != P2M_HEADER.size + 36 * frames:
        raise ValueError('invalid PCSX2 v1 recording length or header')
    for offset in range(P2M_HEADER.size, len(data), 36):
        flags = data[offset:offset + 2]
        yield sum(
            1 << index for index, control in enumerate(CONTROLS)
            if mapping[control] is not None
            and not flags[DUALSHOCK[mapping[control]][0]] & DUALSHOCK[mapping[control]][1]
        )


def load_csv(path, expected_count):
    with path.open(newline='', encoding='utf-8') as source:
        reader = csv.DictReader(source)
        names = reader.fieldnames or []
        if (len(set(names)) != len(names) or not {'frame', 'observed_input'} <= set(names)
                or set(names) - SUPPORTED_METRICS - {'frame'}):
            raise ValueError(f'{path}: CSV requires frame and observed_input, plus known telemetry columns')
        rows = []
        for index, row in enumerate(reader):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'{path}: malformed row {index}')
            if int(row.pop('frame'), 10) != index:
                raise ValueError(f'{path}: frame sequence breaks at row {index}')
            values = {key: int(value, 10) if value else None for key, value in row.items()
                      if value or key in ENEMY_METRICS}
            observed = values.get('observed_input')
            if observed is not None and not 0 <= observed < (1 << len(CONTROLS)):
                raise ValueError(f'{path}: invalid observed input mask at frame {index}')
            rows.append(values)
    if len(rows) != expected_count:
        raise ValueError(f'{path}: expected {expected_count} frame rows, got {len(rows)}')
    return rows


def compare(plan, left, right, fields):
    # Report input and state independently so a late input mismatch cannot hide an earlier state difference.
    def first(find):
        for frame, (expected, a, b) in enumerate(zip(plan, left, right, strict=True)):
            result = find(expected, a, b)
            if result:
                return {'frame': frame, **result}
        return None

    def check_inputs(expected, a, b):
        values = (a.get('observed_input'), b.get('observed_input'))
        if any(value is not None and value != expected for value in values):
            return dict(expected=expected, left=values[0], right=values[1])
        return None

    def check_state(_, a, b):
        differences = {key: [a[key], b[key]] for key in fields if a[key] != b[key]}
        return {'fields': differences} if differences else None

    missing_fields = [
        key for key in fields if any(key not in row for row in left + right)
    ]
    if missing_fields:
        raise ValueError('missing or partially observed telemetry: ' + ', '.join(missing_fields))
    first_input = first(check_inputs)
    first_state = first(check_state)
    observation_gap = next(
        (i for i, (a, b) in enumerate(zip(left, right, strict=True))
         if 'observed_input' not in a or 'observed_input' not in b), None,
    )
    if first_input and (not first_state or first_input['frame'] <= first_state['frame']):
        classification = 'input_desync'
    elif first_state:
        classification = ('unclassified' if observation_gap is not None
                          and observation_gap <= first_state['frame'] else 'gameplay_difference')
    elif observation_gap is not None:
        classification = 'input_unverified'
    else:
        classification = 'match'
    impact = [event['frame'] for event in (first_input, first_state) if event is not None]
    return dict(classification=classification, first_divergent_frame=min(impact) if impact else None,
                first_input=first_input, first_state=first_state, first_unobserved_input=observation_gap)


def verify_context(scenario, scenario_hash, left, right, repeat):
    for context in (left, right):
        if not isinstance(context, dict):
            raise ValueError('run context must be a JSON object')
        required = ('emulator', 'version', 'build', 'checkpoint', 'anchor', 'settings', 'rng')
        if any(key not in context for key in required) or context.get('scenario_sha256') != scenario_hash:
            raise ValueError('run context is incomplete or uses a different scenario')
        if context['anchor'] != scenario['anchor'] or context.get('sampling') != 'post_update':
            raise ValueError('run context has the wrong stage anchor or sampling boundary')
        if not all(isinstance(context[key], str) and context[key] for key in required[:5]):
            raise ValueError('emulator, version, build, checkpoint and anchor must be nonempty strings')
        if not isinstance(context['settings'], dict) or not isinstance(context['rng'], dict):
            raise ValueError('settings and RNG context must be objects')
    if left['settings'] != right['settings']:
        a, b = left['settings'], right['settings']
        keys = sorted(set(a) | set(b))
        details = ', '.join(
            f'{key} (left {a[key]!r}, right {b[key]!r})' if key in a and key in b
            else f'{key} (missing on {"right" if key in a else "left"})'
            for key in keys if key not in a or key not in b or a[key] != b[key]
        )
        raise ValueError(f'logical run settings differ: {details}')
    if repeat and left != right:
        raise ValueError('repeat checks require identical context, including checkpoint and RNG policy')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('mame-plan', 'pcsx2-movie', 'compare', 'ps2-probe-csv'):
        command = commands.add_parser(name)
        command.add_argument('scenario', type=Path)
    commands.choices['mame-plan'].add_argument('output', type=Path)
    movie = commands.choices['pcsx2-movie']
    movie.add_argument('output', type=Path)
    movie.add_argument('--state', type=Path, required=True)
    movie.add_argument('--title', required=True)
    movie.add_argument('--version', default='PCSX2-v2.8.2')
    movie.add_argument('--map', type=Path)
    movie.add_argument('--lead', type=int, default=0)
    movie.add_argument('--tail', type=int, default=0)
    movie.add_argument('--probe-sync', action='store_true',
                       help='prepend four Select frames after lead-in for the homebrew probe')
    decode = commands.add_parser('pcsx2-input')
    decode.add_argument('movie', type=Path)
    decode.add_argument('--map', type=Path)
    report = commands.choices['compare']
    for key in ('left', 'right', 'left_context', 'right_context'):
        report.add_argument(key, type=Path)
    report.add_argument('--fields', nargs='+', required=True,
                        choices=sorted(SUPPORTED_METRICS - {'observed_input'}))
    report.add_argument('--repeat', action='store_true')
    probe = commands.choices['ps2-probe-csv']
    probe.add_argument('ram', type=Path, help='PCSX2 .p2s savestate or raw eeMemory.bin')
    probe.add_argument('output', type=Path)
    start = probe.add_mutually_exclusive_group()
    start.add_argument('--skip', type=int, default=0, help='probe rows preceding scenario frame zero')
    start.add_argument('--find-start', type=int, nargs=2, metavar=('FIRST', 'LAST'),
                       help='find the unique row matching the entire input plan in this inclusive range')
    start.add_argument('--checkpoint', type=Path,
                       help='search from the checkpoint buffer length through eight rows afterward')
    probe.add_argument('--address', type=lambda value: int(value, 0), default=0x01F00000)
    probe.add_argument('--fields', nargs='+', choices=sorted(SUPPORTED_METRICS),
                       default=['observed_input', 'player_x', 'player_y', 'score'])
    args = parser.parse_args()
    try:
        if args.command == 'pcsx2-input':
            for i, mask in enumerate(read_movie(args.movie, load_pad_map(args.map))):
                print(f'{i},{mask}')
            return 0
        scenario, masks, digest = load_plan(args.scenario)
        if args.command == 'mame-plan':
            with args.output.open('x', encoding='ascii') as file:
                file.writelines(f'{mask}\n' for mask in masks)
        elif args.command == 'pcsx2-movie':
            if any(not 0 <= value <= 100_000 for value in (args.lead, args.tail)):
                raise ValueError('lead and tail must be between 0 and 100,000')
            sync = [1 << CONTROLS.index('select')] * 4 if args.probe_sync else []
            write_movie(args.output, sync + masks, load_pad_map(args.map), args.state,
                        args.version, args.title, args.lead, args.tail)
        elif args.command == 'ps2-probe-csv':
            bounds = args.find_start
            if args.checkpoint is not None:
                first = probe_frame_count(read_ee(args.checkpoint), args.address)
                bounds = (first, first + 8)
            selected = probe_to_csv(args.ram, args.output, args.skip, len(masks), args.address, args.fields,
                                    alignment=(bounds, masks) if bounds is not None else None)
            if bounds is not None:
                print(f'Scenario frame 0 matches capture row {selected}')
        else:
            verify_context(scenario, digest, load_json(args.left_context), load_json(args.right_context), args.repeat)
            result = compare(masks, load_csv(args.left, len(masks)), load_csv(args.right, len(masks)), args.fields)
            print(json.dumps(result, indent=2))
            return 0 if result['classification'] == 'match' else 1
        print(f'{len(masks)} frames, scenario SHA-256 {digest}')
        return 0
    except (OSError, ValueError, TypeError, KeyError, struct.error, zipfile.BadZipFile) as exc:
        parser.error(str(exc))


def read_ee(path):
    if not zipfile.is_zipfile(path):
        return path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo('eeMemory.bin')
        if info.file_size != 32 * 1024 * 1024:
            raise ValueError('unexpected PCSX2 EE memory size')
        try:
            return archive.read(info)
        except NotImplementedError:
            if info.compress_type != 93:
                raise ValueError(f'unsupported savestate ZIP method {info.compress_type}') from None
    try:
        import zstandard
    except ImportError:
        raise ValueError('Zstandard savestate requires Python 3.14 or pip install zstandard') from None
    with path.open('rb') as state:
        state.seek(info.header_offset)
        header = state.read(30)
        if header[:4] != b'PK\x03\x04':
            raise ValueError('invalid ZIP member header')
        name_size, extra_size = struct.unpack_from('<HH', header, 26)
        state.seek(name_size + extra_size, 1)
        data = zstandard.ZstdDecompressor().decompress(state.read(info.compress_size),
                                                       max_output_size=info.file_size)
    if len(data) != info.file_size or zlib.crc32(data) != info.CRC:
        raise ValueError('invalid EE memory member size or CRC')
    return data


def select_trace_start(observed, plan, first, last):
    if not 0 <= first <= last:
        raise ValueError('invalid capture row search range')
    if len(set(plan)) < 2:
        raise ValueError('input alignment requires a scenario with at least one control change; use --skip')
    last = min(last, len(observed) - len(plan))
    matches = [offset for offset in range(first, last + 1)
               if observed[offset:offset + len(plan)] == plan]
    if not matches:
        raise ValueError('no complete input plan matches the capture in the requested range')
    if len(matches) != 1:
        raise ValueError(f'input alignment is ambiguous ({len(matches)} matching rows); narrow the search range')
    return matches[0]


def probe_frame_count(data, base):
    if not 0 <= base <= min(len(data), 32 * 1024 * 1024) - 8:
        raise ValueError('invalid EE capture address')
    magic, frames = struct.unpack_from('<II', data, base)
    if magic != 0x46524231 or frames > 2048:
        raise ValueError('invalid PS2 probe buffer')
    return frames


def probe_to_csv(ram, output, skip, count, base, fields, *, alignment=None):
    if len(set(fields)) != len(fields) or 'observed_input' not in fields:
        raise ValueError('expected unique fields including observed_input')
    data = read_ee(ram)
    frames = probe_frame_count(data, base)
    if not 0 <= skip <= frames or skip + count > frames:
        raise ValueError('invalid or incomplete PS2 probe buffer')
    row = struct.Struct('<' + ''.join('i' if field in {'player_x', 'player_y'} else 'I' for field in fields))
    if alignment is not None:
        bounds, plan = alignment
        first, last = bounds
        input_column = fields.index('observed_input')
        captures = row.iter_unpack(data[base + 8:base + 8 + frames * row.size])
        observed = [capture[input_column] for capture in captures]
        if len(observed) != frames:
            raise ValueError('truncated PS2 telemetry')
        skip = select_trace_start(observed, plan, first, last)
    offset = base + 8 + skip * row.size
    rows = list(row.iter_unpack(data[offset:offset + count * row.size]))
    if len(rows) != count:
        raise ValueError('truncated PS2 telemetry')
    with output.open('x', newline='', encoding='ascii') as file:
        writer = csv.writer(file)
        writer.writerow(('frame', *fields))
        for frame, values in enumerate(rows):
            writer.writerow((frame, *(None if key in ENEMY_METRICS and value == 0xFFFFFFFF else value
                                      for key, value in zip(fields, values, strict=True))))
    return skip


if __name__ == '__main__':
    raise SystemExit(main())
