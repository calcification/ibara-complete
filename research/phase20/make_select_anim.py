#!/usr/bin/env python3
"""Phase 20 stage two: Black Label select screen animation from long MAME captures (research/phase20/README.md).

The captures (cap_L.lua / cap_L2.lua style: research/phase20/bl_select_capture_long.lua) hold each state for 240 frames.
Every element of a state settles within ~34 frames of the state's entry (the transition: fly-in, panels appearing)
and then loops with a period of 32 or 64 frames; values change every 2 frames. A state becomes a list of tracks:

    track = sprite, base position, intro samples, loop samples (32 = 64 frames, 1 = constant, 0 = gone after the intro)
    sample = record index; record = position delta, 0x00110B70 flags (blend, flips, alpha), tint, or invisible

sampled every 2 frames from the state's entry. Coordinates, timing, flags and tints only (no pixels).
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_select_data as m  # noqa: E402

LOOP = 32  # samples (64 frames)
H = 240    # frames each state is held in the long captures
S0 = 300   # first input frame (cap_L*.lua)


def frames_ff(fn):
    """frame -> ops, filled forward (the captures only log a frame when its ops change)."""
    d = m.load(fn)
    out, last = {}, None
    for f in range(min(d), max(d) + 1):
        if f in d:
            last = d[f]
        out[f] = last
    return out


def is_head(o):
    return o[4] >= 265


REGIONS = {
    "head": lambda o: is_head(o) and not m.is_digit(o),
    "p1": lambda o: not is_head(o) and o[5] < 120,
    "p2": lambda o: not is_head(o) and o[5] >= 120,
}


def elements(frames, a, b, region):
    """(sprite, occurrence) -> {frame: values}, in BL's draw order: by the element's position in the op list of the
    last frame it is drawn in (elements of the transition only are placed by their last frame's neighbours)."""
    tracks, pos = {}, {}
    for f in range(a, b):
        seen = collections.Counter()
        ops = [o for o in frames[f] or [] if REGIONS[region](o)]
        for i, o in enumerate(ops):
            key = (o[2], o[3], o[6], o[7])
            n = seen[key]
            seen[key] += 1
            tracks.setdefault((key, n), {})[f] = (o[0], o[1], o[4], o[5], o[8], o[9])
            pos[(key, n)] = (i + 0.5) / len(ops)
    return collections.OrderedDict(sorted(tracks.items(), key=lambda kv: pos[kv[0]]))


def settle(seq):
    """first sample index from which seq repeats with period LOOP (seq sampled every 2 frames)."""
    n = len(seq)
    for s in range(0, n - LOOP - 8 + 1):  # at least 8 samples confirm the loop (the join window is short)
        if all(seq[t] == seq[t + LOOP] for t in range(s, n - LOOP)):
            return s
    raise SystemExit("an element does not settle into a 64-frame loop")


def state_tracks(frames, a, region, length=H):
    """Tracks of the state entered at frame a (sampled every 2 frames)."""
    el = elements(frames, a, a + length, region)
    seqs = {k: [v.get(f) for f in range(a, a + length, 2)] for k, v in el.items()}
    intro = max([settle(s) for s in seqs.values()] or [0])
    out = []
    for (key, _n), seq in seqs.items():
        part = seq[:intro + LOOP]
        vis = [x for x in part if x]
        base = (vis[0][2], vis[0][3])
        if len(set(part)) == 1:
            samples, ni, nl = [part[0]], 0, 1
        else:
            loop = part[intro:]
            nl = 0 if all(x is None for x in loop) else (1 if len(set(loop)) == 1 else LOOP)
            samples, ni = part[:intro] + loop[:nl], intro
        out.append({"sprite": key, "base": base, "intro": ni, "loop": nl, "samples": samples})
    return out


def windows(kind, region, frames):
    """state name -> tracks for one long capture (KIND S or P; region p1 or p2)."""
    sfx = "2" if region == "p2" else ""
    other = "P" if kind == "S" else "S"
    st = {}
    st[f"ship_{other}{sfx}"] = state_tracks(frames, S0, region)          # other ship, entered from this one
    st[f"ship_{kind}{sfx}"] = state_tracks(frames, S0 + H, region)       # back: entered from the other ship
    for t in range(4):
        st[f"type_{kind}{sfx}{'ABCD'[t]}"] = state_tracks(frames, S0 + (2 + t) * H, region)
    return st


def build(cap):
    """cap: {"S": L_S, "P": L_P, "S2": L2_S, "P2": L2_P[, "J1": J1]} file names -> {state: tracks}."""
    f = {k: frames_ff(v) for k, v in cap.items()}
    st = {}
    st.update(windows("S", "p1", f["S"]))
    st.update({k: v for k, v in windows("P", "p1", f["P"]).items() if k.startswith("type_")})
    st.update(windows("S", "p2", f["S2"]))
    st.update({k: v for k, v in windows("P", "p2", f["P2"]).items() if k.startswith("type_")})
    first = min(f["S"])
    st["head"] = state_tracks(f["S"], first, "head", S0 - first)
    st["join_P2"] = state_tracks(f["S"], first, "p2", S0 - first)
    st["open_S"] = state_tracks(f["S"], first, "p1", S0 - first)           # player 1 when the screen opens
    st["open_S2"] = state_tracks(f["S2"], 120, "p2", S0 - 120)             # player 2 joining
    if "J1" in f:  # player 2 started alone (bl_select_capture_join_p1.lua): player 1's join panel
        j = f["J1"]
        st["join_P1"] = state_tracks(j, min(j), "p1", S0 - min(j))
    return st


def tables(states, flags_of):
    """Records (dx, dy, flags index, tint index; flags index 255 = invisible), sample indices, flag / tint tables."""
    recs, flags, tints, samples = {}, {}, {}, []
    seqcache = {}
    for name, tracks in states.items():
        for tr in tracks:
            idx = []
            for v in tr["samples"]:
                if v is None:
                    r = (0, 0, 255, 0)
                else:
                    fl = flags.setdefault(flags_of(v[0], v[1]), len(flags))
                    ti = tints.setdefault((v[4] & 0xFF) << 16 | v[5], len(tints))
                    r = (v[2] - tr["base"][0], v[3] - tr["base"][1], fl, ti)
                idx.append(recs.setdefault(r, len(recs)))
            key = tuple(idx)
            if key not in seqcache:
                seqcache[key] = len(samples)
                samples += idx
            tr["seq"] = seqcache[key]
    return recs, flags, tints, samples


if __name__ == "__main__":
    st = build({"S": sys.argv[1], "P": sys.argv[2], "S2": sys.argv[3], "P2": sys.argv[4]})
    recs, flags, tints, samples = tables(st, m.flags_of)
    n = sum(len(v) for v in st.values())
    print(f"{len(st)} states, {n} tracks, {len(recs)} records, {len(flags)} flags, {len(tints)} tints, "
          f"{len(samples)} samples; intro max {max(t['intro'] for v in st.values() for t in v)}")
    dx = [r[0] for r in recs]
    dy = [r[1] for r in recs]
    print("dx", min(dx), max(dx), "dy", min(dy), max(dy))
    print("bytes ~", n * 10 + len(recs) * 4 + len(samples) * 2 + (len(flags) + len(tints)) * 4)
    for k, v in st.items():
        print(k, len(v), "intro", max(t["intro"] for t in v) if v else 0)
