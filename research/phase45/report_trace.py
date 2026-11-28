#!/usr/bin/env python3
"""Compare the replay fixture's checkpoints and optional controller traces."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from p2s_tools import load_ee

CP_BASE = 0x01FC0000
TRACE_BASE = 0x01AC0000
CP = struct.Struct("<8I")
TRACE = struct.Struct("<18I")
SYNC_FIELDS = (
    "forced_record_retries", "early_blocks", "withheld_checks",
    "render_holds", "timeouts", "cursor_misses",
)
TRACE_FIELDS = (
    "scroll", "step", "cursor", "wait", "position", "animation", "kind", "active",
    "calls", "result", "spawn_tick", "spawn_scroll", "spawn_seed", "spawn_cursor",
    "resource_checks", "resources_ready", "pool_checks", "pool_ready",
)


def rows(mem, base, step, fmt, limit, side):
    return [fmt.unpack_from(mem, base + (side * step + i) * fmt.size) for i in range(limit)]


def first_difference(a, b, key_names):
    for i, (before, after) in enumerate(zip(a, b)):
        changes = {key: [f"{x:#x}", f"{y:#x}"] for key, x, y in zip(key_names, before, after) if x != y}
        if changes:
            return {"row": i, "changes": changes}
    return None


def analyze(mem, rp, controller):
    magic, mode, recorded, played, overflow, count_a, count_b, tick_miss = struct.unpack_from("<8I", mem, rp)
    if magic != 0x33504552 or mode != 1 or not 0 < recorded <= 20000 or played < recorded:
        raise ValueError("expected a completed record/playback capture")
    if overflow or min(count_a, count_b) < 1 or max(count_a, count_b) > 1400:
        raise ValueError("invalid checkpoint counts or replay overflow")
    a, b = (rows(mem, CP_BASE, 1400, CP, n, side) for side, n in enumerate((count_a, count_b)))
    before = {row[0]: row[1:] for row in a if row[0] < recorded}
    after = {row[0]: row[1:] for row in b if row[0] < recorded}
    if before.keys() != after.keys() or not before:
        raise ValueError("checkpoint coverage differs between recording and playback")
    keys = sorted(before)
    bad = [update for update in keys if before[update] != after[update]]
    fields = ("score", "rank", "stage_tick", "rng", "x", "y", "bombs")
    result = dict(recorded=recorded, played=played, compared=len(keys), tick_miss=tick_miss,
                  mismatches=len(bad), first_checkpoint=bad[0] if bad else None,
                  first_by_field={name: next((i for i in bad if before[i][idx] != after[i][idx]), None)
                                  for idx, name in enumerate(fields)})
    if controller:
        limit = min(1200, recorded)
        a, b = (rows(mem, TRACE_BASE, 1200, TRACE, limit, side) for side in range(2))
        result["stage_clock"] = first_difference([r[:4] for r in a], [r[:4] for r in b], TRACE_FIELDS[:4])
        result["slot_3"] = first_difference([r[4:8] for r in a], [r[4:8] for r in b], TRACE_FIELDS[4:8])
        result["factory"] = [
            [dict(update=i, **dict(zip(TRACE_FIELDS[8:], row[8:]))) for i, row in enumerate(side) if row[8]]
            for side in (a, b)
        ]
    return result


def verify_sync(report, scenario):
    stats = report["controller_sync"]
    if stats["timeouts"] or stats["cursor_misses"]:
        return "controller synchronization fell back to the native update"
    if scenario == "early" and not stats["early_blocks"]:
        return "playback never encountered early assets"
    if scenario == "late" and not stats["render_holds"]:
        return "playback never waited for late assets"
    outcomes = [[(e["update"], e["calls"], bool(e["result"])) for e in side]
                for side in report["factory"]]
    if outcomes[0] != outcomes[1] or not any(success for _, _, success in outcomes[0]):
        return "type-76 factory outcomes differ or no creation was captured"
    if report["stage_clock"] or report["slot_3"]:
        return "stage clock or type-76 slot diverged"
    if report["mismatches"] or report["tick_miss"]:
        return "gameplay checkpoints or update timing diverged"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("symbols", type=Path)
    parser.add_argument("--controller-trace", action="store_true")
    parser.add_argument("--factory-events", action="store_true", help="include every retry in the report")
    parser.add_argument("--expect-controller-sync", choices=("aligned", "early", "late"),
                        help="fail on replay drift or if the specified timing case was not exercised")
    args = parser.parse_args()
    syms = json.loads(args.symbols.read_text())
    sync_addr = syms.get("replay_controller_sync_stats")
    if args.expect_controller_sync and sync_addr is None:
        parser.error("--expect-controller-sync requires symbols from a --sync-controller build")
    mem = load_ee(args.state)
    report = analyze(mem, syms["rp"], args.controller_trace or bool(args.expect_controller_sync))
    if sync_addr is not None:
        sync = struct.unpack_from("<6I", mem, sync_addr)
        report["controller_sync"] = dict(zip(SYNC_FIELDS, sync))
    if args.expect_controller_sync:
        report["sync_failure"] = verify_sync(report, args.expect_controller_sync)
    if "factory" in report and not args.factory_events:
        report["factory"] = [dict(
            attempts=sum(event["calls"] for event in events),
            first_attempt=events[0] if events else None,
            first_success=next((event for event in events if event["result"]), None),
            first_native_ready_update=next((e["update"] for e in events if e["resources_ready"]), None),
            resource_failures=sum(e["resource_checks"] - e["resources_ready"] for e in events),
            slot_failures=sum(e["pool_checks"] - e["pool_ready"] for e in events),
        ) for events in report["factory"]]
    print(json.dumps(report, indent=2))
    return int(bool(report.get("sync_failure")))


if __name__ == "__main__":
    sys.exit(main())
