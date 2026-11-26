"""Pack shipped Lua name -> native call-site/table references into R6XRF.

    python tools/engine/lua_xref_catalog.py \
        --out build/tmp/lua_xrefs.r6xrf

Rows follow docs/recon/LUA_API.md order and use bindings.json, derived from
RIP-relative string operands and pointer-table reads in wmn6r.exe.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REPORT = os.path.join(ROOT, "docs", "recon", "bindings.json")

MAGIC = b"R6XRF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8sIIII")
ROW = struct.Struct("<IIIIII")
TABLE = struct.Struct("<IIII")
VIA = {"code": 0, "table": 1, "pointer": 2}
KIND = {"strings": 0, "pointer": 1}


def collect(report=REPORT):
    import lua_globals_catalog  # noqa: E402
    _categories, names = lua_globals_catalog.collect()
    with open(report, "r", encoding="utf8") as stream:
        bindings = json.load(stream)
    assert len(bindings) == 219
    rows = []
    for row in names:
        name = row["name"]
        binding = bindings[name]
        assert binding["via"] in VIA
        tables = []
        for item in binding.get("tables", []):
            assert item["kind"] in KIND
            tables.append({"rva": item["rva"], "kind": KIND[item["kind"]],
                           "users": list(item["users"])})
        rows.append({"name": name, "via": VIA[binding["via"]],
                     "funcs": list(binding.get("funcs", [])),
                     "tables": tables})
    return rows


def build(rows):
    arrays_base = HEADER.size + ROW.size * len(rows)
    arrays = bytearray()

    def alloc(values):
        offset = arrays_base + len(arrays)
        arrays.extend(struct.pack("<%dI" % len(values), *values) if values
                      else b"")
        return offset

    records = []
    for row in rows:
        funcs_off = alloc(row["funcs"])
        table_offsets = []
        for table in row["tables"]:
            users_off = alloc(table["users"])
            table_offsets.append(alloc([table["rva"], table["kind"],
                                        len(table["users"]), users_off]))
        records.append((row, funcs_off, table_offsets))
    strings_off = arrays_base + len(arrays)
    strings = bytearray()

    def add_string(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("utf8") + b"\0")
        return offset

    payload = b""
    for row, funcs_off, table_offsets in records:
        payload += ROW.pack(add_string(row["name"]), row["via"],
                            len(row["funcs"]), funcs_off,
                            len(table_offsets),
                            table_offsets[0] if table_offsets else 0)
    return (HEADER.pack(MAGIC, VERSION, len(rows), strings_off,
                        len(strings)) + payload + bytes(arrays) +
            bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.report)
    blob = build(rows)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d names, %d function refs, %d table refs, %d bytes" %
          (args.out, len(rows), sum(len(row["funcs"]) for row in rows),
           sum(len(row["tables"]) for row in rows), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
