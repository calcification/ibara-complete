#!/usr/bin/env python3
"""Ibara KURO patcher: turns your own 'Ibara (Japan).iso' (SLPM-66301) into the Ibara KURO disc.

    python3 apply_kuro_patch.py "Ibara (Japan).iso" "Ibara KURO.iso"

Windows: drag your ISO onto apply_kuro_patch.bat (or run: py apply_kuro_patch.py "Ibara (Japan).iso" out.iso).
Needs only Python 3.8+ (no extra packages) and ~3.7 GB of free disk space. Your ISO is only read.

The patch (ibara_kuro.patch, next to this script) holds this project's changes and copy instructions; every
game byte comes from your disc. The result is checked against the SHA-256 of the disc the patch was made from.
"""
import hashlib
import struct
import sys
import zlib
from pathlib import Path

MAGIC = b"IBKPATCH1\0"
HERE = Path(__file__).resolve().parent


def read_patch(path):
    raw = path.read_bytes()
    if not raw.startswith(MAGIC):
        raise SystemExit(f"{path} is not an Ibara KURO patch")
    body = zlib.decompress(raw[len(MAGIC):])
    src_size, dst_size = struct.unpack_from("<QQ", body, 0)
    src_md5, dst_sha = body[16:32].hex(), body[32:64].hex()
    p = 64
    n = body[p]
    note = body[p + 1:p + 1 + n].decode(errors="replace")
    p += 1 + n
    count, = struct.unpack_from("<I", body, p)
    p += 4
    records = []
    for _ in range(count):
        at, length, nops = struct.unpack_from("<QII", body, p)
        p += 16
        ops = []
        for _ in range(nops):
            kind = body[p]
            if kind == 0:
                src, ln = struct.unpack_from("<QI", body, p + 1)
                ops.append((0, src, ln))
                p += 13
            else:
                ln, = struct.unpack_from("<I", body, p + 1)
                ops.append((1, body[p + 5:p + 5 + ln]))
                p += 5 + ln
        records.append((at, length, ops))
    return src_size, dst_size, src_md5, dst_sha, note, records


def digest(path, algo, label):
    h = hashlib.new(algo)
    size = path.stat().st_size
    done = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
            done += len(chunk)
            if done % (1 << 28) < (1 << 22):
                print(f"\r    {label} {done * 100 // size:3d}%", end="", flush=True)
    print(f"\r    {label} 100%")
    return h.hexdigest()


def write_iso(source, output, dst_size, dst_sha, records):
    """Copy the disc sparsely and remove an incomplete output if writing or verification fails."""
    zeros = bytes(1 << 22)
    with source.open("rb") as src, output.open("xb") as out:
        try:
            while True:
                block = src.read(len(zeros))
                if not block:
                    break
                if block == zeros[:len(block)]:
                    out.seek(len(block), 1)
                else:
                    out.write(block)
            out.truncate(dst_size)
            for at, length, ops in records:
                buf = bytearray()
                for op in ops:
                    if op[0] == 0:
                        src.seek(op[1])
                        buf += src.read(op[2])
                    else:
                        buf += op[1]
                if len(buf) != length:
                    raise SystemExit("Patch is damaged (record length mismatch).")
                out.seek(at)
                out.write(buf)
            out.flush()
            print("3/3 verifying ...")
            if digest(output, "sha256", "SHA-256") != dst_sha:
                raise SystemExit("Verification failed. Re-download the patch and try again.")
        except BaseException:
            out.close()
            output.unlink(missing_ok=True)
            raise


def main(argv):
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    source = Path(argv[0])
    output = Path(argv[1])
    patch = Path(argv[2]) if len(argv) == 3 else HERE / "ibara_kuro.patch"
    if output.exists():
        raise SystemExit(f"{output} already exists; choose a new name")
    src_size, dst_size, src_md5, dst_sha, note, records = read_patch(patch)
    print(f"Ibara KURO patch: {note}")
    print("1/3 checking your ISO ...")
    if source.stat().st_size != src_size or digest(source, "md5", "MD5") != src_md5:
        raise SystemExit("This is not the retail Japanese 'Ibara (Japan).iso' (SLPM-66301, MD5 " + src_md5 + ").")
    print("2/3 writing the new ISO ...")
    write_iso(source, output, dst_size, dst_sha, records)
    print(f"Done: {output}")
    print("Boot it, press Start at the title; KURO is the third row of Mode Select (Circle to enter).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
