"""Pack shipped plain string-pointer runs into an R6NTR blob.

    python tools/engine/name_runs_catalog.py \
        --out build/tmp/name_runs.r6ntr

Facts come from docs/recon/name_tables.json: 521 runs, 13,283 names and 888
code references. Only RVAs, counts and names are packed; no executable bytes
are copied.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "name_tables.json")

MAGIC = b"R6NTR\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s5I")
RUN = struct.Struct("<7I")
WORD = struct.Struct("<I")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    runs = data["strings"]
    names = [name for run in runs for name in run["names"]]
    users = [rva for run in runs for rva in run["users"]]
    assert len(runs) == 521
    assert len(names) == sum(run["count"] for run in runs) == 13283
    assert len(users) == 888
    assert all(len(run["names"]) == run["count"] for run in runs)
    return runs, names, users


def build(runs, names, users):
    user_off = HEADER.size + RUN.size * len(runs)
    name_off = user_off + WORD.size * len(users)
    strings_off = name_off + WORD.size * len(names)
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    name_offsets = [add(name) for name in names]
    first_name = 0
    first_user = 0
    run_payload = bytearray()
    for run in runs:
        run_payload.extend(RUN.pack(
            run["rva"], run["size"], run["stride"], run["count"],
            first_name, first_user, len(run["users"])))
        first_name += run["count"]
        first_user += len(run["users"])

    header = HEADER.pack(MAGIC, VERSION, len(runs), len(names), len(users),
                         len(strings))
    return (header + bytes(run_payload) +
            b"".join(WORD.pack(rva) for rva in users) +
            b"".join(WORD.pack(offset) for offset in name_offsets) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    runs, names, users = collect(args.report)
    blob = build(runs, names, users)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d runs, %d names, %d code refs, %d bytes" %
          (args.out, len(runs), len(names), len(users), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
