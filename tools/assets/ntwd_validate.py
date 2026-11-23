"""Validate NTWD texture parsing over a directory of XMD.001 .tex files.

    python tools/assets/ntwd_validate.py DIR [--limit N]

Checks that every texture header has a GIDX chunk and that its pixel blob is
inside the stream. Prints format, bpp and dimension histograms.
"""

import argparse
import collections
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from xmd_streams import load, parse  # noqa: E402
from ntwd_texture import parse_stream  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.directory, "**", "*.tex"), recursive=True))
    if args.limit:
        paths = paths[:args.limit]
    stats = collections.Counter()
    fmts = collections.Counter()
    bpps = collections.Counter()
    bad = []
    for p in paths:
        b, how = load(p, False)
        if how != "gzip":
            stats["not_gzip"] += 1
            continue
        try:
            _, offsets = parse(b)
        except ValueError as exc:
            bad.append((p, "container", str(exc)))
            continue
        for i, start in enumerate(offsets):
            end = offsets[i + 1] if i + 1 < len(offsets) else len(b)
            d = b[start:end]
            try:
                info = parse_stream(d)
            except ValueError as exc:
                bad.append((p, "stream%d" % i, str(exc)))
                continue
            stats["streams"] += 1
            stats["textures"] += info["count"]
            for t in info["textures"]:
                fmts[t["fmt"]] += 1
                bpp = t["data_size"] * 8 / max(1, t["width"] * t["height"])
                bpps[round(bpp, 2)] += 1
                at = t["header"] + t["data_off"]
                if at + t["data_size"] > len(d):
                    bad.append((p, "blob%d" % i, "range outside stream"))
                else:
                    stats["blobs_ok"] += 1

    print("files=%d %s" % (len(paths), dict(stats)))
    print("fmt=%s" % sorted(fmts.items()))
    print("bpp=%s" % sorted(bpps.items()))
    print("bad=%d" % len(bad))
    for p, where, why in bad[:20]:
        print("  %s %s %s" % (p, where, why))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
