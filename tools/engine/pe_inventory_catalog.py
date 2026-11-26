"""Pack shipped PE and .pdata recon facts into an R6PEI blob.

    python tools/engine/pe_inventory_catalog.py \
        --out build/tmp/pe_inventory.r6pei

Facts come from docs/recon/pe.json and pdata.json, derived from the shipped
wmn6r.exe. Only counts, RVAs, names and ordinals are packed; no executable
bytes are committed or decoded here.
"""

import argparse
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PE_REPORT = os.path.join(ROOT, "docs", "recon", "pe.json")
PDATA_REPORT = os.path.join(ROOT, "docs", "recon", "pdata.json")

MAGIC = b"R6PEI\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s28I")
FUNC = struct.Struct("<4I")
DLL = struct.Struct("<3I")
IMPORT = struct.Struct("<3I")
NAME = struct.Struct("<I")
SECTION = struct.Struct("<6I")
TLS = struct.Struct("<2I")


def collect(pe_report=PE_REPORT, pdata_report=PDATA_REPORT):
    with open(pe_report, "r", encoding="utf8") as stream:
        pe = json.load(stream)
    with open(pdata_report, "r", encoding="utf8") as stream:
        pdata = json.load(stream)
    funcs = pdata["list"]
    assert pe["pdata"]["count"] == len(funcs) == pdata["functions"]
    assert len(pe["imports"]) == 28
    assert sum(len(item["functions"]) for item in pe["imports"]) == 825
    assert len(pe["exports"]) == 2
    assert len(pe["tls"]["callbacks"]) == 1
    assert len(pe["sections"]) == 7
    return pe, pdata, funcs


def build(pe, pdata, funcs):
    dll_off = HEADER.size + FUNC.size * len(funcs)
    import_off = dll_off + DLL.size * len(pe["imports"])
    section_off = import_off + IMPORT.size * 825
    export_off = section_off + SECTION.size * len(pe["sections"])
    tls_off = export_off + NAME.size * len(pe["exports"])
    strings_off = tls_off + TLS.size * len(pe["tls"]["callbacks"])

    strings = bytearray()

    def add(value):
        offset = strings_off + len(strings)
        strings.extend(value.encode("ascii") + b"\0")
        return offset

    func_payload = bytearray()
    for row in funcs:
        assert row["end"] > row["rva"] and row["size"] == row["end"] - row["rva"]
        func_payload.extend(FUNC.pack(row["rva"], row["end"], row["size"],
                                      1 if row["leaf"] else 0))

    import_payload = bytearray()
    dll_rows = []
    for item in pe["imports"]:
        first = len(import_payload) // IMPORT.size
        for func in item["functions"]:
            if "ordinal" in func:
                import_payload.extend(IMPORT.pack(1, func["ordinal"], 0))
            else:
                import_payload.extend(IMPORT.pack(0, 0,
                                                  add(func["name"])))
        dll_rows.append(DLL.pack(add(item["dll"]), first,
                                 len(item["functions"])))

    section_payload = b"".join(
        SECTION.pack(add(section["name"]), section["vsize"],
                     section["vaddr"], section["raw_size"],
                     section["raw_ptr"], section["characteristics"])
        for section in pe["sections"])
    export_payload = b"".join(NAME.pack(add(name))
                              for name in pe["exports"])
    tls_payload = b"".join(
        TLS.pack(int(callback, 16) & 0xffffffff,
                 int(callback, 16) >> 32)
        for callback in pe["tls"]["callbacks"])
    guid_off = add(pe["debug"]["pdb"]["guid"])
    path_off = add(pe["debug"]["pdb"]["path"])

    base = int(pe["image_base"], 16)
    header = HEADER.pack(
        MAGIC, VERSION, pe["size"], int(pe["machine"], 16),
        int(pe["magic"], 16), pe["timestamp"], base & 0xffffffff,
        base >> 32, int(pe["entry_rva"], 16), pe["size_of_image"],
        len(pe["directories"]), pe["pdata"]["count"],
        pe["pdata"]["unique_unwind"], pdata["code_bytes"],
        pdata["text_bytes"], pdata["leaf"], pdata["chained"],
        pdata["with_eh"], pe["relocations"]["blocks"],
        pe["relocations"]["entries"], len(pe["imports"]), 825,
        len(pe["exports"]), len(pe["tls"]["callbacks"]),
        len(pe["sections"]), len(strings), guid_off,
        pe["debug"]["pdb"]["age"], path_off)
    return (header + bytes(func_payload) + b"".join(dll_rows) +
            bytes(import_payload) + section_payload + export_payload +
            tls_payload + bytes(strings))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pe", default=PE_REPORT)
    parser.add_argument("--pdata", default=PDATA_REPORT)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    pe, pdata, funcs = collect(args.pe, args.pdata)
    blob = build(pe, pdata, funcs)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%s: %d functions, %d imports, %d sections, %d bytes" %
          (args.out, len(funcs), 825, len(pe["sections"]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
