"""Pack the shipped BGM id/name/path table into a C-readable blob.

    python tools/engine/bgm_catalog.py --dump D:\\Games\\W6W-05 \
        --out build\\tmp\\bgm.r6bgm

Rows come from `wmn6r.exe` VAs 0x141e1f8e0 (path pointers) and 0x1414ec550
(fixed 0x40-byte names), recovered by `tools/engine/audio_events.py`. No game
data is committed; the output is derived data for the freestanding core.
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402

MAGIC = b"R6BGM\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIII")
RECORD = struct.Struct("<HHII")

FLAG_STOP = 0x0001
FLAG_RANDOM = 0x0002


def collect(dump):
    return audio_events.build(dump)["bgm"]


def build(rows):
    items = []
    for row in rows:
        flags = 0
        if row["id"] == audio_events.BGM_NO_SOUND:
            flags |= FLAG_STOP
        if row["id"] == audio_events.BGM_RANDOM:
            flags |= FLAG_RANDOM
        items.append((row["id"], flags, row["name"], row["path"]))

    strings_off = HEADER.size + len(items) * RECORD.size
    strings = bytearray(b"\0")
    offsets = {b"": strings_off}

    def intern(value):
        encoded = value.encode("utf8") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = strings_off + len(strings)
            strings.extend(encoded)
        return offsets[encoded]

    records = bytearray()
    for bgm_id, flags, name, path in items:
        records.extend(RECORD.pack(bgm_id, flags, intern(name), intern(path)))

    return HEADER.pack(MAGIC, VERSION, len(items), items[0][0], strings_off,
                       len(strings), 0) + bytes(records) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d BGM ids, %d bytes" % (args.out, len(rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
