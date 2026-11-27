"""Pack structured SM4 control flow from shipped NSXR records into R6SCF.

    python tools/engine/shader_control_flow_catalog.py \
        --dump D:\\Games\\W6W-05 --out build/tmp/shader_control.r6scf

Facts come from nsxr_shader.control_flow() on the shipped SHDR instructions.
No branch targets are invented and no GLSL translation is stored.
"""

import argparse
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

import nsxr_shader  # noqa: E402

MAGIC = b"R6SCF\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
RECORD = struct.Struct("<6I")
BLOCK = struct.Struct("<10I")
CASE = struct.Struct("<2I")
INDEX = struct.Struct("<I")

KIND = {"if": 0, "loop": 1, "switch": 2}
CASE_KIND = {"case": 0, "default": 1}
NO_ELSE = 0xFFFFFFFF


def collect(dump):
    shaders = nsxr_shader.collect(dump)["shaders"]
    rows = []
    unmatched = []
    for name, shader in sorted(shaders.items()):
        for record in shader["records"]:
            code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                        if chunk["tag"] == "SHDR")
            result = nsxr_shader.control_flow(code["instructions"])
            assert not result["unmatched"]
            rows.append({
                "name": name,
                "stage": record["index"],
                "blocks": result["blocks"],
                "unmatched": result["unmatched"],
            })
            unmatched.extend(result["unmatched"])
    return rows, unmatched


def build(rows, unmatched):
    blocks = bytearray()
    cases = bytearray()
    indices = bytearray()
    strings = bytearray(b"\0")
    offsets = {b"": 0}

    def intern(value):
        encoded = value.encode("utf8") + b"\0"
        if encoded not in offsets:
            offsets[encoded] = len(strings)
            strings.extend(encoded)
        return offsets[encoded]

    records = bytearray()
    for row in rows:
        first_block = len(blocks) // BLOCK.size
        unmatched_first = len(indices) // INDEX.size
        for value in row["unmatched"]:
            indices.extend(INDEX.pack(value))
        for block in row["blocks"]:
            case_first = len(cases) // CASE.size
            for case in block["cases"]:
                cases.extend(CASE.pack(CASE_KIND[case["kind"]], case["start"]))
            break_first = len(indices) // INDEX.size
            for value in block["breaks"]:
                indices.extend(INDEX.pack(value))
            continue_first = len(indices) // INDEX.size
            for value in block["continues"]:
                indices.extend(INDEX.pack(value))
            blocks.extend(BLOCK.pack(
                KIND[block["kind"]], block["start"], block["end"],
                block.get("else", NO_ELSE), case_first,
                len(block["cases"]), break_first, len(block["breaks"]),
                continue_first, len(block["continues"])))
        records.extend(RECORD.pack(
            intern(row["name"]), row["stage"], first_block,
            len(row["blocks"]), unmatched_first, len(row["unmatched"])))

    record_off = HEADER.size
    block_off = record_off + len(records)
    case_off = block_off + len(blocks)
    index_off = case_off + len(cases)
    string_off = index_off + len(indices)
    for position in range(0, len(records), RECORD.size):
        fields = list(RECORD.unpack_from(records, position))
        fields[0] += string_off
        fields[4] += index_off // INDEX.size
        RECORD.pack_into(records, position, *fields)
    for position in range(0, len(blocks), BLOCK.size):
        fields = list(BLOCK.unpack_from(blocks, position))
        fields[4] += case_off // CASE.size
        fields[6] += index_off // INDEX.size
        fields[8] += index_off // INDEX.size
        BLOCK.pack_into(blocks, position, *fields)
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(blocks) // BLOCK.size,
        len(cases) // CASE.size, len(indices) // INDEX.size, record_off,
        block_off, case_off, index_off, string_off, len(strings))
    return header + bytes(records + blocks + cases + indices + strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows, unmatched = collect(args.dump)
    blob = build(rows, unmatched)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%d records, %d blocks, %d bytes: %s" %
          (len(rows), sum(len(row["blocks"]) for row in rows),
           len(blob), args.out))


if __name__ == "__main__":
    main()
