"""Pack the story keys hard-coded by wmn6r.exe.

    python tools/engine/story_keys_catalog.py --exe D:\\Games\\W6W-05\\wmn6r.exe \
        --dump D:\\Games\\W6W-05 --out build/tmp/story_keys.r6sk

Evidence: f_4a3680 / f_4a3730 at RVA 0x4a3680 / 0x4a3730 use
`drive_story_2_0` directly and index a 100-pointer table at RVA 0x12ffd20.
The table holds `drive_story_TipsEnd00`..`drive_story_TipsEnd99`. Every name is
checked against data_jp/msgdb/msgdb.lua; the 546 other message-DB keys have no
observed direct or table reference in these two functions. No dialogue or
unlock semantics are inferred.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))

from pe_report import PE  # noqa: E402
import story_catalog  # noqa: E402

MAGIC = b"R6SK\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIIIIII")
RECORD = struct.Struct("<IHBBII")
HEADER_SIZE = HEADER.size
RECORD_SIZE = RECORD.size

TABLE_RVA = 0x12FFD20
TABLE_COUNT = 100
DIRECT_KEYS = ("drive_story_2_0",)
SOURCE_DIRECT = 1
SOURCE_TABLE = 2
NO_TABLE_INDEX = 0xFFFFFFFF


def native_rows(exe):
    pe = PE(exe)
    offset = pe.off(TABLE_RVA)
    if offset is None:
        raise ValueError("story-key pointer table not in a raw section")
    rows = [{"name": name, "source": SOURCE_DIRECT,
             "table_index": NO_TABLE_INDEX} for name in DIRECT_KEYS]
    for index in range(TABLE_COUNT):
        value = struct.unpack_from("<Q", pe.raw, offset + index * 8)[0]
        name = pe.cstr(value - pe.image_base)
        if not name:
            raise ValueError("empty story-key table entry %d" % index)
        rows.append({"name": name, "source": SOURCE_TABLE,
                     "table_index": index})
    if len({row["name"] for row in rows}) != len(rows):
        raise ValueError("duplicate native story key")
    return rows


def msgdb_keys(dump):
    text = story_catalog.read_text(
        os.path.join(dump, story_catalog.MSGDB), "utf-8-sig")
    return {key for key, _ in story_catalog.MSG_RE.findall(text)
            if story_catalog.STORY_KEY.match(key)}


def collect(exe, dump):
    rows = native_rows(exe)
    keys = msgdb_keys(dump)
    matched = sum(1 for row in rows if row["name"] in keys)
    if matched != len(rows):
        raise ValueError("%d/%d native keys missing from msgdb.lua" %
                         (len(rows) - matched, len(rows)))
    return {"rows": rows, "msgdb_count": len(keys), "matched": matched}


def build(data):
    strings = bytearray()
    offsets = {}
    rows = data["rows"]

    def add(text):
        raw = text.encode("ascii")
        if raw in offsets:
            return offsets[raw], len(raw)
        offset = len(strings)
        offsets[raw] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    payload = bytearray()
    for row in rows:
        offset, length = add(row["name"])
        payload.extend(RECORD.pack(offset, length, row["source"], 0,
                                   row["table_index"], 0))
    strings_offset = HEADER_SIZE + len(payload)
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), TABLE_COUNT, data["msgdb_count"],
        data["matched"], len(strings), strings_offset)
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
    data = collect(args.exe, args.dump)
    blob = build(data)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
    print("%s: %d native keys (%d direct, %d table), %d msgdb keys, "
          "%d bytes" % (args.out, len(data["rows"]), len(DIRECT_KEYS),
                        TABLE_COUNT, data["msgdb_count"], len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
