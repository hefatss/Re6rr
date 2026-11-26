"""Pack shipped luaL_Reg tables into an R6LREG blob.

    python tools/engine/lua_reg_tables_catalog.py \
        --out build/tmp/lua_reg_tables.r6lreg

Facts come from docs/recon/name_tables.json: three tables with 42 name/function
rows and one code reference. Signature-like labels are copied verbatim and
are not interpreted.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "name_tables.json")

MAGIC = b"R6LREG\0\1"
VERSION = 1
HEADER = struct.Struct("<8s5I")
TABLE = struct.Struct("<7I")
ENTRY = struct.Struct("<2I")
WORD = struct.Struct("<I")


def collect(report=REPORT):
    with open(report, "r", encoding="utf8") as stream:
        data = json.load(stream)
    tables = data["reg"]
    entries = [entry for table in tables for entry in table["entries"]]
    users = [rva for table in tables for rva in table["users"]]
    assert len(tables) == 3
    assert len(entries) == 42
    assert len(users) == 1
    assert all(table["size"] == table["count"] * table["stride"]
               for table in tables)
    return tables, entries, users


def build(tables, entries, users):
    entry_off = HEADER.size + TABLE.size * len(tables)
    user_off = entry_off + ENTRY.size * len(entries)
    strings_off = user_off + WORD.size * len(users)
    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    first_entry = 0
    first_user = 0
    table_payload = bytearray()
    for table in tables:
        table_payload.extend(TABLE.pack(
            table["rva"], table["size"], table["stride"], table["count"],
            first_entry, first_user, len(table["users"])))
        first_entry += table["count"]
        first_user += len(table["users"])

    entry_payload = b"".join(
        ENTRY.pack(add(name), func_rva) for name, func_rva in entries)
    header = HEADER.pack(MAGIC, VERSION, len(tables), len(entries),
                         len(users), len(strings))
    return (header + bytes(table_payload) + entry_payload +
            b"".join(WORD.pack(rva) for rva in users) + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    tables, entries, users = collect(args.report)
    blob = build(tables, entries, users)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d tables, %d entries, %d code refs, %d bytes" %
          (args.out, len(tables), len(entries), len(users), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
