"""Classify the game's asset files by extension and by container magic.

    python tools/recon/assets_report.py [--game PATH] [--out DIR]

Nothing is extracted to disk: gzip members are inflated in memory far enough to
read the inner header. Answers:

* which extensions exist, how many, how much space;
* which are gzip (the model/texture files start with 1f 8b 08), and what magic
  the inflated payload begins with (NTWD, XMD.001, ...);
* which are plain containers or raw data (course .bin looks like float32 arrays);
* what the shader folder actually holds (source or precompiled DXBC).

Writes <out>/assets.json and prints a summary.
"""

import argparse
import collections
import gzip
import json
import os
import struct
import sys

MAGIC_NAMES = {
    b"NTWD": "NTWD",
    b"XMD\x00": "XMD",
    b"XMD.": "XMD",
    b"BM": "BMP",
    b"\x89PNG": "PNG",
    b"DDS ": "DDS",
    b"RIFF": "RIFF",
    b"OggS": "OGG",
    b"BKHD": "BINK",
    b"BIKi": "BINK",
    b"ID3": "MP3",
    b"\xff\xfb": "MP3",
    b"PK\x03\x04": "ZIP",
    b"<?xm": "XML",
    b"<htm": "HTML",
    b"\x00\x00\x00\x01": "MPEG/AVC?",
    b"DXBC": "DXBC",
}


def detect(b):
    if len(b) >= 4:
        if b[:4] == b"DXBC":
            return "DXBC"
        for m, name in MAGIC_NAMES.items():
            if b.startswith(m):
                return name
    if b[:2] == b"\x1f\x8b":
        return "gzip"
    if b[:4] == b"\x00\x00\x00\x00":
        return "zeros"
    printable = sum(1 for c in b[:64] if 32 <= c < 127 or c in (9, 10, 13))
    if printable > 60:
        return "text"
    return "raw"


def float_ratio(b, n=256):
    n = min(len(b) // 4, n)
    if n == 0:
        return 0.0
    ok = 0
    for i in range(n):
        v = struct.unpack_from("<f", b, 4 * i)[0]
        if v == v and abs(v) < 1e7 and abs(v) > 1e-9:
            ok += 1
    return ok / n


def classify_file(path, size):
    with open(path, "rb") as f:
        head = f.read(64)
    kind = detect(head)
    info = {"kind": kind, "inner": None}
    if kind == "gzip":
        try:
            with gzip.open(path, "rb") as g:
                inner = g.read(64)
            info["inner"] = detect(inner)
            info["inner_head"] = inner[:8].hex()
        except (OSError, EOFError):
            info["inner"] = "gzip-error"
    elif kind == "raw" and size >= 64:
        info["float_ratio"] = round(float_ratio(head), 2)
    return info


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=r"D:\Games\W6W-05")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(here)), "docs", "recon"))
    ap.add_argument("--max-files", type=int, default=0, help="stop classifying after N files (0 = all)")
    args = ap.parse_args()

    report = {"roots": []}
    for base in (os.path.join(args.game, "data"), os.path.join(args.game, "data_jp")):
        if not os.path.isdir(base):
            continue
        ext_count = collections.Counter()
        ext_bytes = collections.Counter()
        ext_kind = collections.defaultdict(collections.Counter)
        inner = collections.Counter()
        top = collections.defaultdict(lambda: {"files": 0, "bytes": 0})
        shader = []
        classified = 0
        for dp, dn, fn in os.walk(base):
            rel = os.path.relpath(dp, base)
            first = rel.split(os.sep)[0]
            for f in fn:
                p = os.path.join(dp, f)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                ext = os.path.splitext(f)[1].lower() or "(none)"
                ext_count[ext] += 1
                ext_bytes[ext] += size
                top[first]["files"] += 1
                top[first]["bytes"] += size
                if args.max_files and classified >= args.max_files:
                    continue
                classified += 1
                try:
                    info = classify_file(p, size)
                except OSError:
                    continue
                ext_kind[ext][info["kind"]] += 1
                if info["inner"]:
                    inner[info["inner"]] += 1
                if "/shader/" in p.replace("\\", "/") or "\\shader\\" in p:
                    if len(shader) < 40:
                        shader.append({"path": os.path.relpath(p, base), "size": size, "kind": info["kind"],
                                       "inner": info["inner"], "head": open(p, "rb").read(16).hex()})
        report["roots"].append({
            "root": base,
            "extensions": [{"ext": e, "files": n, "bytes": ext_bytes[e], "kinds": dict(ext_kind[e])}
                           for e, n in ext_count.most_common()],
            "inner_magics": inner.most_common(),
            "top_folders": sorted(({"name": k, **v} for k, v in top.items()), key=lambda d: -d["bytes"]),
            "shader_samples": shader,
            "classified": classified,
        })
        print("==", base)
        print("   extensions:", ", ".join("%s:%d" % (e, n) for e, n in ext_count.most_common(14)))
        print("   inner     :", ", ".join("%s:%d" % kv for kv in inner.most_common(12)))
        print("   top rows  :", ", ".join("%s %.1fMB" % (d["name"], d["bytes"] / 1048576) for d in report["roots"][-1]["top_folders"][:8]))

    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, "assets.json")
    with open(dst, "w", encoding="utf8") as f:
        json.dump(report, f, indent=1)
    print("wrote", dst)


if __name__ == "__main__":
    sys.exit(main())
