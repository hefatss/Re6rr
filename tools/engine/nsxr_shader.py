"""Inventory and extract DXBC bytecode from shipped `NSXR` shader blobs.

    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --report build/tmp/shaders.json --list
    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --extract Body.nsh --stage 0 --out build/tmp/body_dxbc.bin

`.nsh` files are raw `NSXR` containers. Each has two records; a record points
0x20 bytes ahead of a DirectX bytecode (`DXBC`) blob. No game data is stored in
this repository.
"""

import argparse
import json
import os
import struct

MAGIC = b"NSXR"
DXBC_MAGIC = b"DXBC"
HEADER_SIZE = 0x80
RECORD_SIZE = 16
SHADER_DIR = os.path.join("data", "shader", "nsh")


def parse_dxbc(raw, offset):
    if raw[offset:offset + 4] != DXBC_MAGIC:
        raise ValueError("missing DXBC at 0x%x" % offset)
    if offset + 0x20 > len(raw):
        raise ValueError("short DXBC header at 0x%x" % offset)
    digest = raw[offset + 4:offset + 0x14]
    version, size, chunk_count = struct.unpack_from("<3I", raw, offset + 0x14)
    if size < 0x20 or offset + size > len(raw):
        raise ValueError("bad DXBC size 0x%x at 0x%x" % (size, offset))
    if offset + 0x20 + chunk_count * 4 > offset + size:
        raise ValueError("bad DXBC chunk table at 0x%x" % offset)
    offsets = struct.unpack_from("<%dI" % chunk_count, raw, offset + 0x20)
    chunks = []
    for relative in offsets:
        start = offset + relative
        if start + 8 > offset + size:
            raise ValueError("DXBC chunk outside blob at 0x%x" % start)
        tag = raw[start:start + 4]
        chunk_size, = struct.unpack_from("<I", raw, start + 4)
        if start + 8 + chunk_size > offset + size:
            raise ValueError("DXBC chunk %r overruns blob" % tag)
        chunks.append({
            "tag": tag.decode("ascii", "replace"),
            "offset": relative,
            "size": chunk_size,
            "data_offset": start + 8,
        })
    return {
        "digest": digest.hex(),
        "version": version,
        "size": size,
        "chunks": chunks,
        "raw_offset": offset,
    }


def parse_signature(raw, chunk):
    start = chunk["data_offset"]
    if chunk["size"] < 8:
        raise ValueError("short signature chunk %r" % chunk["tag"])
    count, marker = struct.unpack_from("<2I", raw, start)
    entries = []
    for index in range(count):
        position = start + 8 + index * 24
        if position + 24 > start + chunk["size"]:
            raise ValueError("signature entry outside %r" % chunk["tag"])
        name_offset, semantic_index, unknown, type_field, register, mask = \
            struct.unpack_from("<6I", raw, position)
        name_start = start + name_offset
        end = raw.find(b"\0", name_start, start + chunk["size"])
        if end < 0 or name_start < start:
            raise ValueError("bad signature name in %r" % chunk["tag"])
        entries.append({
            "name": raw[name_start:end].decode("ascii", "replace"),
            "semantic_index": semantic_index,
            "unknown": unknown,
            "type_field": type_field,
            "register": register,
            "mask": mask,
        })
    return {"marker": marker, "entries": entries}


def parse_nsh(path):
    with open(path, "rb") as stream:
        raw = stream.read()
    if len(raw) < HEADER_SIZE or raw[:4] != MAGIC:
        raise ValueError("bad NSXR header: %s" % path)
    file_size, version, subversion = struct.unpack_from("<3I", raw, 4)
    if file_size != len(raw):
        raise ValueError("NSXR size %d, file %d: %s" %
                         (file_size, len(raw), path))
    flags, record_count = struct.unpack_from("<2I", raw, 0x20)
    table = struct.unpack_from("<5I", raw, 0x28)
    records = []
    for index in range(record_count):
        entry = 0x80 + index * RECORD_SIZE
        if entry + RECORD_SIZE > len(raw):
            raise ValueError("NSXR record table truncated: %s" % path)
        offset, count, dxbc_size, reserved = struct.unpack_from(
            "<4I", raw, entry)
        dxbc_offset = offset + 0x20
        blob = parse_dxbc(raw, dxbc_offset)
        if blob["size"] != dxbc_size:
            raise ValueError("NSXR[%d] size %d, DXBC %d: %s" %
                             (index, dxbc_size, blob["size"], path))
        for chunk in blob["chunks"]:
            if chunk["tag"] in ("ISGN", "OSGN"):
                chunk["signature"] = parse_signature(raw, chunk)
        records.append({
            "index": index,
            "offset": offset,
            "count": count,
            "dxbc_size": dxbc_size,
            "reserved": reserved,
            "dxbc": blob,
        })
    return {
        "file": os.path.basename(path),
        "size": file_size,
        "version": version,
        "subversion": subversion,
        "flags": flags,
        "record_count": record_count,
        "table": table,
        "records": records,
    }


def collect(dump):
    root = os.path.join(dump, SHADER_DIR)
    shaders = {}
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if name.endswith(".nsh") and os.path.isfile(path):
            shaders[name] = parse_nsh(path)
    return {"shaders": shaders}


def extract(dump, name, index, output):
    header = parse_nsh(os.path.join(dump, SHADER_DIR, name))
    if index < 0 or index >= header["record_count"]:
        raise ValueError("stage %d outside %s" % (index, name))
    record = header["records"][index]
    blob = record["dxbc"]
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(os.path.join(dump, SHADER_DIR, name), "rb") as source, \
            open(output, "wb") as target:
        source.seek(blob["raw_offset"])
        target.write(source.read(blob["size"]))
    return record


def report_text(data):
    shaders = data["shaders"]
    records = [record for shader in shaders.values()
               for record in shader["records"]]
    chunks = {}
    for record in records:
        for chunk in record["dxbc"]["chunks"]:
            chunks[chunk["tag"]] = chunks.get(chunk["tag"], 0) + 1
    sizes = [record["dxbc_size"] for record in records]
    return "\n".join([
        "%d .nsh files, %d DXBC blobs, %d..%d bytes" %
        (len(shaders), len(records), min(sizes), max(sizes)),
        "chunks: %s" % ", ".join("%s=%d" % item
                                 for item in sorted(chunks.items())),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extract")
    parser.add_argument("--stage", type=int, default=0)
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.extract:
        record = extract(args.dump, args.extract, args.stage,
                         args.out or os.path.join("build", "tmp",
                                                  "shader.dxbc"))
        print("extracted %s[%d]: %d bytes, %s" %
              (args.extract, args.stage, record["dxbc_size"],
               [chunk["tag"] for chunk in record["dxbc"]["chunks"]]))
        return 0

    data = collect(args.dump)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
    print(report_text(data) if args.list else
          report_text(data).splitlines()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
