"""Pack shipped SHDR cbuffer/resource usage into an R6SCU blob.

    python tools/engine/shader_usage_catalog.py \
        --dump D:\\Games\\W6W-05 --out build/tmp/shader_usage.r6scu

Facts come from nsxr_shader.uniform_usage() and resource_usage() on the shipped
SHDR instructions and RDEF reflection. They are usage maps, not translations.
"""

import argparse
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

import nsxr_shader  # noqa: E402

MAGIC = b"R6SCU\0\1\0"
VERSION = 1
HEADER = struct.Struct("<8s11I")
RECORD = struct.Struct("<11I")
NAMED_COUNT = struct.Struct("<2I")
NAMED = struct.Struct("<I")


def collect(dump):
    shaders = nsxr_shader.collect(dump)["shaders"]
    rows = []
    for name, shader in sorted(shaders.items()):
        for record in shader["records"]:
            uniforms = nsxr_shader.uniform_usage(record)
            resources = nsxr_shader.resource_usage(record)
            rows.append({
                "name": name,
                "stage": record["index"],
                "uniforms": uniforms["usage"],
                "dynamic_cbuffer": uniforms["dynamic"],
                "resources": resources["usage"],
                "declared": resources["declared"],
                "dynamic_resource": resources["dynamic"],
                "unmapped_resource": resources["unmapped"],
            })
    return rows


def build(rows):
    uniforms = bytearray()
    resources = bytearray()
    declared = bytearray()
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
        uniform_first = len(uniforms) // NAMED_COUNT.size
        for name, count in sorted(row["uniforms"].items()):
            uniforms.extend(NAMED_COUNT.pack(intern(name), count))
        resource_first = len(resources) // NAMED_COUNT.size
        for name, count in sorted(row["resources"].items()):
            resources.extend(NAMED_COUNT.pack(intern(name), count))
        declared_first = len(declared) // NAMED.size
        for name in row["declared"]:
            declared.extend(NAMED.pack(intern(name)))
        records.extend(RECORD.pack(
            intern(row["name"]), row["stage"], uniform_first,
            len(row["uniforms"]), row["dynamic_cbuffer"], resource_first,
            len(row["resources"]), declared_first, len(row["declared"]),
            row["dynamic_resource"], row["unmapped_resource"]))

    record_off = HEADER.size
    uniform_off = record_off + len(records)
    resource_off = uniform_off + len(uniforms)
    declared_off = resource_off + len(resources)
    string_off = declared_off + len(declared)
    for position in range(0, len(records), RECORD.size):
        fields = list(RECORD.unpack_from(records, position))
        fields[0] += string_off
        RECORD.pack_into(records, position, *fields)
    for table in (uniforms, resources):
        for position in range(0, len(table), NAMED_COUNT.size):
            name_off, count = NAMED_COUNT.unpack_from(table, position)
            NAMED_COUNT.pack_into(table, position, string_off + name_off, count)
    for position in range(0, len(declared), NAMED.size):
        NAMED.pack_into(declared, position,
                        string_off + NAMED.unpack_from(declared, position)[0])
    header = HEADER.pack(
        MAGIC, VERSION, len(rows), len(uniforms) // NAMED_COUNT.size,
        len(resources) // NAMED_COUNT.size,
        len(declared) // NAMED.size, record_off, uniform_off, resource_off,
        declared_off, string_off, len(strings))
    return header + bytes(records + uniforms + resources + declared + strings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = collect(args.dump)
    blob = build(rows)
    with open(args.out, "wb") as stream:
        stream.write(blob)
    print("%d records, %d bytes: %s" % (len(rows), len(blob), args.out))


if __name__ == "__main__":
    main()
