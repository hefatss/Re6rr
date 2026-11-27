r"""Pack the complete MessageID namespace from msgdb.lua.

    python tools/engine/msgdb_namespace_catalog.py \
        --dump D:\Games\W6W-05 --out build/tmp/msgdb_namespace.r6mns

Every ASCII MessageID in data_jp/msgdb/msgdb.lua is copied with its byte
offset and first-four-character group. The 647 drive_story_ keys keep their
known subset count; no dialogue, scene or unlock mapping is inferred.
"""

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_catalog as sc  # noqa: E402
import story_keys_catalog as skc  # noqa: E402

MAGIC = b"R6MNS\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s6I")
RECORD = struct.Struct("<4I")
GROUP = struct.Struct("<I")
EXPECTED_COUNT = 31021
EXPECTED_GROUPS = 58
EXPECTED_SIZE = 3876598
EXPECTED_STORY = 647
GROUP_LENGTH = 4


def collect(dump):
    path = os.path.join(dump, sc.MSGDB)
    with open(path, "rb") as stream:
        raw = stream.read()
    if len(raw) != EXPECTED_SIZE:
        raise ValueError("unexpected msgdb.lua size %d" % len(raw))
    text = sc.read_text(path, "utf-8-sig")
    matches = [(match.start(), match.group(1))
               for match in sc.MSG_RE.finditer(text)]
    names = [name for _, name in matches]
    if (len(matches), len(set(names))) != (EXPECTED_COUNT, EXPECTED_COUNT):
        raise ValueError("expected %d unique MessageIDs, found %d/%d" %
                         (EXPECTED_COUNT, len(matches), len(set(names))))
    if any(not name.isascii() for name in names):
        raise ValueError("non-ASCII MessageID")
    story = sum(1 for name in names if sc.STORY_KEY.match(name))
    if story != EXPECTED_STORY or story != len(skc.msgdb_keys(dump)):
        raise ValueError("drive_story subset mismatch")
    groups = sorted({name[:GROUP_LENGTH] for name in names})
    if len(groups) != EXPECTED_GROUPS:
        raise ValueError("expected %d groups, found %d" %
                         (EXPECTED_GROUPS, len(groups)))
    group_index = {name: at for at, name in enumerate(groups)}
    rows = [(offset, name, group_index[name[:GROUP_LENGTH]])
            for offset, name in matches]
    return rows, groups


def build(rows, groups):
    strings_base = (HEADER.size + len(rows) * RECORD.size +
                    len(groups) * GROUP.size)
    strings = bytearray()
    offsets = {}

    def add(value):
        raw = value.encode("ascii")
        found = offsets.get(raw)
        if found is not None:
            return found, len(raw)
        offset = strings_base + len(strings)
        offsets[raw] = offset
        strings.extend(raw + b"\0")
        return offset, len(raw)

    records = bytearray()
    for byte_offset, name, group in rows:
        offset, length = add(name)
        records.extend(RECORD.pack(offset, length, byte_offset, group))
    group_offsets = bytearray()
    for name in groups:
        offset, length = add(name)
        if length != GROUP_LENGTH:
            raise ValueError("bad group name %r" % name)
        group_offsets.extend(GROUP.pack(offset))
    header = HEADER.pack(MAGIC, VERSION, len(rows), len(groups),
                         len(strings), EXPECTED_SIZE, EXPECTED_STORY)
    return header + bytes(records) + bytes(group_offsets) + bytes(strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    rows, groups = collect(args.dump)
    blob = build(rows, groups)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    if args.report:
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"groups": groups, "count": len(rows),
                       "bytes": len(blob)}, stream, indent=2)
    print("%s: %d MessageIDs, %d groups, %d bytes" %
          (args.out, len(rows), len(groups), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
