#!/usr/bin/env python3
"""Record one MAME scenario, replay its native movie twice, and verify the traces."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from replay import compare, load_csv, load_plan


def run(args):
    scenario, plan, digest = load_plan(args.scenario)
    executable = shutil.which(args.mame)
    if executable is None:
        raise ValueError('MAME executable not found')
    executable = str(Path(executable).resolve())
    script = Path(__file__).with_name('mame.lua').resolve()
    rom = args.rompath.resolve() / 'ibarablk.zip'
    with rom.open('rb') as source:
        rom_hash = hashlib.file_digest(source, 'sha256').hexdigest()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    path = out / 'plan.txt'
    path.write_text(''.join(f'{mask}\n' for mask in plan), encoding='ascii')
    environment = dict(os.environ, REPLAY_PLAN=str(path), REPLAY_START=str(args.start),
                       REPLAY_REQUIRE_BULLETS=str(int(args.require_bullets)))
    environment.setdefault('SDL_VIDEODRIVER', 'dummy')
    environment.setdefault('SDL_AUDIODRIVER', 'dummy')
    for name, address in [('XTC', args.xtc_address), ('RNG', args.rng_address)]:
        key = f'REPLAY_{name}_ADDRESS'
        environment.pop(key, None)
        if address is not None:
            if not 0 <= address <= 0xFFFFFFFC or address % 4:
                raise ValueError(f'{name} address must be an aligned 32-bit address')
            environment[key] = str(address)
    if args.xtc_divisor < 1:
        raise ValueError('XTC divisor must be positive')
    environment['REPLAY_XTC_DIVISOR'] = str(args.xtc_divisor)
    build = subprocess.check_output([executable, '-version'], env=environment, text=True).strip()
    context = {
        'emulator': 'MAME', 'version': build, 'build': 'ibarablk sha256:' + rom_hash,
        'checkpoint': f'clean factory boot, sample clock {args.start}',
        'anchor': scenario['anchor'], 'scenario_sha256': digest, 'sampling': 'post_update',
        'settings': {'stage': 1, 'difficulty': 'factory default', 'ship': 'default selection'},
        'rng': {'policy': 'natural cold boot', 'initial': None},
        'telemetry': {'xtc_address': args.xtc_address, 'xtc_divisor': args.xtc_divisor,
                      'rng_address': args.rng_address},
    }
    (out / 'context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    flags = [
        executable, 'ibarablk', '-rompath', str(rom.parent), '-noreadconfig',
        '-nonvram_save', '-nvram_directory', str(out / 'nvram'),
        '-cfg_directory', str(out / 'cfg'), '-video', 'none', '-sound', 'none',
        '-nothrottle', '-skip_gameinfo', '-autoboot_script', str(script),
    ]
    traces = []
    for mode, name in [('record', 'record'), ('playback', 'playback-1'), ('playback', 'playback-2')]:
        trace = out / f'{name}.csv'
        env = dict(environment, REPLAY_MODE=mode, REPLAY_OUT=str(trace))
        with (out / f'{name}.log').open('wb') as log:
            try:
                subprocess.run(flags + ['-' + mode, 'test.inp'], env=env, cwd=out,
                               stdout=log, stderr=subprocess.STDOUT, timeout=150, check=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                raise ValueError(f'MAME {name} failed; see {out / (name + ".log")}') from error
        traces.append(load_csv(trace, len(plan)))
    initial = traces[0][0]
    context['settings'].update({key: initial[key] for key in ('bomb_stock', 'lives')})
    context['frame_zero'] = {key: initial[key] for key in ('player_x', 'player_y', 'rank', 'hostile_bullets', 'enemies')}
    if args.rng_address is not None:
        context['rng']['frame_zero'] = initial['rng']
    (out / 'context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    fields = [f for f in traces[0][0] if f != 'observed_input']
    reports = [compare(plan, traces[0], candidate, fields) for candidate in traces[1:]]
    result = json.dumps(reports, indent=2)
    (out / 'repeat.json').write_text(result + '\n', encoding='utf-8')
    print(result)
    return 0 if all(report['classification'] == 'match' for report in reports) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', type=Path)
    parser.add_argument('output', type=Path, help='new private output directory')
    parser.add_argument('--mame', default='mame')
    parser.add_argument('--rompath', type=Path, required=True)
    parser.add_argument('--start', type=int, default=3101, help='absolute MAME callback for scenario frame zero')
    parser.add_argument('--require-bullets', action='store_true')
    parser.add_argument('--xtc-address', type=lambda value: int(value, 0))
    parser.add_argument('--xtc-divisor', type=int, default=1)
    parser.add_argument('--rng-address', type=lambda value: int(value, 0))
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
