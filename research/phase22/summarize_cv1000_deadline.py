"""Compare pre-IRQ draw gates with the next refresh's gameplay advance."""
import argparse
from collections import Counter
import csv
from itertools import pairwise
import json
from pathlib import Path


LIST_PUBLISHED = 0x19671010


def summarize(path: Path) -> dict:
    with path.open(newline="") as source:
        samples = list(csv.DictReader(source))
    if len(samples) < 2:
        raise ValueError(f"{path} needs at least two refresh samples")

    counts = {"advance": Counter(), "hold": Counter()}
    first_hold = None
    for sample, following in pairwise(samples):
        frame = int(sample["frame"])
        irq_delta = (int(following["irq_outer"]) - int(sample["irq_outer"])) & 0xFFFFFFFF
        tick_delta = int(following["tick"]) - int(sample["tick"])
        if (following["window"] != sample["window"] or int(following["frame"]) != frame + 1
                or irq_delta != 1 or tick_delta not in (0, 1)):
            raise ValueError(f"{path} has unexpected cadence after refresh {frame}")

        published = int(sample["pending"], 16) == LIST_PUBLISHED
        ready = bool(int(sample["ready"]))
        gates = {
            (False, False): "neither_ready",
            (False, True): "list_unpublished",
            (True, False): "blitter_busy",
            (True, True): "both_ready",
        }[published, ready]
        counts["advance" if tick_delta else "hold"][gates] += 1
        if not tick_delta and first_hold is None:
            first_hold = frame + 1

    return {"window": samples[0]["window"], "intervals": len(samples) - 1,
            "first_hold": first_hold, **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps([summarize(path) for path in args.trace], indent=2))


if __name__ == "__main__":
    main()
