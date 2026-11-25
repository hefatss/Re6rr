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


def read_name(raw, start, limit):
    if start >= limit:
        raise ValueError("name offset 0x%x outside chunk" % start)
    end = raw.find(b"\0", start, limit)
    if end < 0:
        raise ValueError("unterminated name at 0x%x" % start)
    return raw[start:end].decode("ascii", "replace")


STAGE_NAMES = {
    0xfffe: "vertex", 0xffff: "pixel", 0x4753: "geometry",
    0x4853: "hull", 0x4453: "domain", 0x4353: "compute",
}
CLASS_NAMES = {0: "scalar", 1: "vector", 2: "matrix_rows",
               3: "matrix_columns", 4: "object", 5: "struct"}
TYPE_NAMES = {0: "void", 1: "bool", 2: "int", 3: "float", 4: "string",
              19: "uint"}
RESOURCE_NAMES = {0: "cbuffer", 1: "tbuffer", 2: "texture", 3: "sampler",
                  4: "uav_typed"}


def parse_rdef(raw, chunk):
    start = chunk["data_offset"]
    end = start + chunk["size"]
    if chunk["size"] < 0x1c:
        raise ValueError("short RDEF chunk")
    cb_count, cb_offset, res_count, res_offset = struct.unpack_from(
        "<4I", raw, start)
    target, stage = struct.unpack_from("<2H", raw, start + 0x10)
    flags, creator_offset = struct.unpack_from("<2I", raw, start + 0x14)
    sm5 = target >= 0x500
    res_stride = 36 if target >= 0x501 else 32
    var_stride = 40 if sm5 else 24
    # ponytail: SM5 nameOffset fields handled, no struct-member recursion.
    resources = []
    for index in range(res_count):
        position = start + res_offset + index * res_stride
        if position + res_stride > end:
            raise ValueError("RDEF resource outside chunk")
        fields = list(struct.unpack_from("<8I", raw, position))
        entry = {
            "name": read_name(raw, start + fields[0], end),
            "type": RESOURCE_NAMES.get(fields[1], fields[1]),
            "return_type": fields[2], "dimension": fields[3],
            "sample_count": fields[4], "bind_point": fields[5],
            "bind_count": fields[6], "flags": fields[7],
        }
        if res_stride == 36:
            entry["space"], entry["id"] = fields[8:10]
        resources.append(entry)
    cbuffers = []
    for index in range(cb_count):
        position = start + cb_offset + index * 24
        if position + 24 > end:
            raise ValueError("RDEF cbuffer outside chunk")
        name_offset, var_count, var_offset, size, cb_flags, cb_type = \
            struct.unpack_from("<6I", raw, position)
        variables = []
        for variable in range(var_count):
            entry = start + var_offset + variable * var_stride
            if entry + var_stride > end:
                raise ValueError("RDEF variable outside chunk")
            vals = struct.unpack_from("<6I", raw, entry)
            type_start = start + vals[4]
            if type_start + 16 > end:
                raise ValueError("RDEF type outside chunk")
            var_class, var_type, rows, cols, elements, members = \
                struct.unpack_from("<6H", raw, type_start)
            member_offset, = struct.unpack_from("<I", raw, type_start + 12)
            type_name_offset = 0x20 if sm5 else 0x10
            type_name = ""
            if member_offset or sm5:
                if sm5:
                    type_name_offset, = struct.unpack_from(
                        "<I", raw, type_start + 0x20)
                if type_name_offset:
                    type_name = read_name(raw, start + type_name_offset, end)
            variables.append({
                "name": read_name(raw, start + vals[0], end),
                "offset": vals[1], "size": vals[2], "flags": vals[3],
                "type": {
                    "class": CLASS_NAMES.get(var_class, var_class),
                    "type": TYPE_NAMES.get(var_type, var_type),
                    "rows": rows, "cols": cols, "elements": elements,
                    "members": members, "member_offset": member_offset,
                    "name": type_name,
                },
                "default_offset": vals[5],
            })
        cbuffers.append({
            "name": read_name(raw, start + name_offset, end),
            "size": size, "flags": cb_flags, "type": cb_type,
            "variables": variables,
        })
    return {
        "target_version": target,
        "stage": STAGE_NAMES.get(stage, hex(stage)),
        "flags": flags,
        "creator": read_name(raw, start + creator_offset, end),
        "cbuffers": cbuffers,
        "resources": resources,
    }


STAT_FIELDS = [
    "instruction_count", "temp_register_count", "unknown_a", "dcl_count",
    "flt_instruction_count", "int_instruction_count", "uint_instruction_count",
    "static_flow_control_count", "dynamic_flow_control_count", "unknown_b",
    "temp_array_count", "array_instruction_count", "cut_instruction_count",
    "emit_instruction_count", "sample_tex_count", "load_tex_count",
    "cmp_tex_count", "sample_bias_tex_count", "sample_grad_tex_count",
    "mov_instruction_count", "unknown_c", "conv_instruction_count",
    "unknown_d", "input_prim_count", "gs_output_topology",
    "gs_max_output_vtx_count", "unknown_e0", "unknown_e1", "unknown_e2",
    "unknown_f", "c_control_points", "hs_output_prim", "hs_partitioning",
    "tessellator_domain", "unknown_g0", "unknown_g1", "unknown_g2",
]


def parse_stat(raw, chunk):
    count = chunk["size"] // 4
    if chunk["size"] % 4 or count > len(STAT_FIELDS):
        raise ValueError("unsupported STAT size 0x%x" % chunk["size"])
    words = struct.unpack_from("<%dI" % count, raw, chunk["data_offset"])
    return dict(zip(STAT_FIELDS, words))


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
            elif chunk["tag"] == "RDEF":
                chunk["reflection"] = parse_rdef(raw, chunk)
            elif chunk["tag"] == "STAT":
                chunk["statistics"] = parse_stat(raw, chunk)
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
    reflections = [chunk["reflection"] for record in records
                   for chunk in record["dxbc"]["chunks"]
                   if chunk["tag"] == "RDEF"]
    stages = {}
    for reflection in reflections:
        stages[reflection["stage"]] = stages.get(reflection["stage"], 0) + 1
    cbuffers = sum(len(item["cbuffers"]) for item in reflections)
    variables = sum(len(cb["variables"]) for item in reflections
                    for cb in item["cbuffers"])
    resources = sum(len(item["resources"]) for item in reflections)
    return "\n".join([
        "%d .nsh files, %d DXBC blobs, %d..%d bytes" %
        (len(shaders), len(records), min(sizes), max(sizes)),
        "chunks: %s" % ", ".join("%s=%d" % item
                                 for item in sorted(chunks.items())),
        "reflection: %s, %d cbuffers, %d variables, %d resources" %
        (", ".join("%s=%d" % item for item in sorted(stages.items())),
         cbuffers, variables, resources),
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
