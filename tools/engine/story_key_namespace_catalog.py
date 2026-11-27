r"""Pack the complete drive_story_* MessageID namespace from msgdb.lua.

    python tools/engine/story_key_namespace_catalog.py \
        --exe D:\Games\W6W-05\wmn6r.exe \
        --dump D:\Games\W6W-05 --out build/tmp/story_key_namespace.r6skn

Every ASCII `drive_story_` key in data_jp/msgdb/msgdb.lua is copied. The 101
keys directly or table-referenced by the shipped executable keep their source
and table index; the other 546 are marked message-DB-only. No dialogue, scene
or unlock mapping is inferred.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import story_keys_catalog as skc  # noqa: E402

MAGIC = b"R6SKN\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIIII")
RECORD = struct.Struct("<IIBB2xII")
SOURCE_MSGDB_ONLY = 0
EXPECTED_KEYS = 647
EXPECTED_NATIVE = 101
EXPECTED_MSGDB_ONLY = 546


def collect(exe, dump):
    native = {row["name"]: row for row in skc.native_rows(exe)}
    keys = skc.msgdb_keys(dump)
    if len(keys) != EXPECTED_KEYS or len(native) != EXPECTED_NATIVE:
        raise ValueError("expected %d msgdb and %d native keys, found %d/%d" %
                         (EXPECTED_KEYS, EXPECTED_NATIVE, len(keys),
                          len(native)))
    if not set(native).issubset(keys):
        raise ValueError("native keys missing from msgdb.lua")
    rows = []
    for name in sorted(keys):
        if not name.isascii():
            raise ValueError("non-ASCII story key: %s" % name)
        row = native.get(name)
        if row is None:
            rows.append({"name": name, "source": SOURCE_MSGDB_ONLY,
                         "table_index": skc.NO_TABLE_INDEX})
        else:
            rows.append({"name": name, "source": row["source"],
                         "table_index": row["table_index"]})
    msgdb_only = sum(row["source"] == SOURCE_MSGDB_ONLY for row in rows)
    if msgdb_only != EXPECTED_MSGDB_ONLY:
        raise ValueError("expected %d msgdb-only keys, found %d" %
                         (EXPECTED_MSGDB_ONLY, msgdb_only))
    return rows


def build(rows):
    strings = bytearray()
    payload = bytearray()
    offsets = {}
    strings_offset = HEADER.size + len(rows) * RECORD.size
    for row in rows:
        raw = row["name"].encode("ascii")
        offset = offsets.get(raw)
        if offset is None:
            offset = strings_offset + len(strings)
            offsets[raw] = offset
            strings.extend(raw + b"\0")
        payload.extend(RECORD.pack(offset, len(raw), row["source"], 0,
                                   row["table_index"], 0))
    header = HEADER.pack(MAGIC, VERSION, len(rows), EXPECTED_NATIVE,
                         len(strings), HEADER.size, strings_offset, 0)
    return header + bytes(payload) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default=os.path.join(
        r"D:\Games\W6W-05", "wmn6r.exe"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    rows = collect(args.exe, args.dump)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(rows, stream, indent=2)
    print("%s: %d drive_story keys (%d native, %d msgdb-only), %d bytes" %
          (args.out, len(rows), EXPECTED_NATIVE, EXPECTED_MSGDB_ONLY,
           len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
