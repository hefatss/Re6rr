"""Inventory and extract DXBC bytecode from shipped `NSXR` shader blobs.

    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --report build/tmp/shaders.json --list
    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --extract Body.nsh --stage 0 --out build/tmp/body_dxbc.bin

`.nsh` files are raw `NSXR` containers. Each has two records; a record points
0x20 bytes ahead of a DirectX bytecode (`DXBC`) blob. SHDR tokens are decoded
into instructions, declarations and SM4 operands (register type, mask/swizzle,
immediate and relative indices, neg/abs modifiers). No game data is stored in
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


OPCODE_NAMES = [
    "ADD", "AND", "BREAK", "BREAKC", "CALL", "CALLC", "CASE", "CONTINUE",
    "CONTINUEC", "CUT", "DEFAULT", "DERIV_RTX", "DERIV_RTY", "DISCARD",
    "DIV", "DP2", "DP3", "DP4", "ELSE", "EMIT", "EMITTHENCUT", "ENDIF",
    "ENDLOOP", "ENDSWITCH", "EQ", "EXP", "FRC", "FTOI", "FTOU", "GE",
    "IADD", "IF", "IEQ", "IGE", "ILT", "IMAD", "IMAX", "IMIN", "IMUL",
    "INE", "INEG", "ISHL", "ISHR", "ITOF", "LABEL", "LD", "LD_MS", "LOG",
    "LOOP", "LT", "MAD", "MIN", "MAX", "CUSTOMDATA", "MOV", "MOVC", "MUL",
    "NE", "NOP", "NOT", "OR", "RESINFO", "RET", "RETC", "ROUND_NE",
    "ROUND_NI", "ROUND_PI", "ROUND_Z", "RSQ", "SAMPLE", "SAMPLE_C",
    "SAMPLE_C_LZ", "SAMPLE_L", "SAMPLE_D", "SAMPLE_B", "SQRT", "SWITCH",
    "SINCOS", "UDIV", "ULT", "UGE", "UMUL", "UMAD", "UMAX", "UMIN", "USHR",
    "UTOF", "XOR", "DCL_RESOURCE", "DCL_CONSTANT_BUFFER", "DCL_SAMPLER",
    "DCL_INDEX_RANGE", "DCL_GS_OUTPUT_PRIMITIVE_TOPOLOGY",
    "DCL_GS_INPUT_PRIMITIVE", "DCL_MAX_OUTPUT_VERTEX_COUNT", "DCL_INPUT",
    "DCL_INPUT_SGV", "DCL_INPUT_SIV", "DCL_INPUT_PS", "DCL_INPUT_PS_SGV",
    "DCL_INPUT_PS_SIV", "DCL_OUTPUT", "DCL_OUTPUT_SGV", "DCL_OUTPUT_SIV",
    "DCL_TEMPS", "DCL_INDEXABLE_TEMP", "DCL_GLOBAL_FLAGS", "RESERVED0",
    "LOD", "GATHER4", "SAMPLE_POS", "SAMPLE_INFO",
]
SHADER_TYPES = ["pixel", "vertex", "geometry", "hull", "domain", "compute"]

# SM4 operand encoding from DXBC: token bits 0..1 component count, 2..3
# selection mode, 4..7 mask, 4..11 swizzle, 12..19 type, 20..21 index
# dimension, 22..30 index representations, bit 31 extended modifier.
OPERAND_TYPES = [
    "temp", "input", "output", "indexable_temp", "immediate32",
    "immediate64", "sampler", "resource", "constant_buffer",
    "immediate_constant_buffer", "label", "input_primitiveid",
    "output_depth", "null", "rasterizer", "output_coverage_mask", "stream",
    "function_body", "function_table", "interface", "function_input",
    "function_output", "output_control_point_id", "input_fork_instance_id",
    "input_join_instance_id", "input_control_point", "output_control_point",
    "input_patch_constant", "input_domain_point", "this_pointer",
    "unordered_access_view", "thread_group_shared_memory", "input_thread_id",
    "input_thread_group_id", "input_thread_id_in_group", "input_coverage_mask",
    "input_thread_id_in_group_flattened", "input_gs_instance_id",
    "output_depth_greater_equal", "output_depth_less_equal", "cycle_counter",
    "output_stencil_ref", "inner_coverage",
]
SELECTION_MODES = ["mask", "swizzle", "select1"]
COMPONENT_NAMES = "xyzw"
NUM_COMPONENT_NAMES = ["scalar", "one", "four", "n"]
INDEX_TYPES = ["immediate32", "immediate64", "relative",
               "immediate32_plus_relative", "immediate64_plus_relative"]
MODIFIER_NAMES = ["none", "neg", "abs", "absneg"]
PRECISION_NAMES = ["default", "float16", "float10", "unused", "sint16",
                   "uint16", "any16", "any10"]
EXTENDED_OPCODE_TYPES = ["empty", "sample_controls", "resource_dim",
                         "resource_return_type"]

# Operand counts for the SM4 opcodes in OPCODE_NAMES. Declarations use
# DECL_OPERAND_COUNTS below; CUSTOMDATA is not an instruction.
OPERAND_COUNTS = {}
for _ops, _count in (
        ((2, 7, 9, 10, 18, 19, 20, 21, 22, 23, 48, 58, 62), 0),
        ((3, 4, 6, 8, 13, 31, 44, 63, 76), 1),
        ((5, 11, 12, 25, 26, 27, 28, 40, 43, 47, 54, 59, 64, 65, 66, 67,
          68, 75, 86, 111), 2),
        ((0, 1, 14, 15, 16, 17, 24, 29, 30, 32, 33, 34, 36, 37, 38, 39,
          41, 42, 45, 49, 51, 52, 56, 57, 60, 61, 77, 78, 79, 80, 81, 83,
          84, 85, 87, 110), 3),
        ((35, 46, 50, 55, 69, 82, 108, 109), 4),
        ((70, 71, 72, 74), 5),
        ((73,), 6)):
    for _opcode in _ops:
        OPERAND_COUNTS[_opcode] = _count

# DCL_TEMPS, DCL_INDEXABLE_TEMP and DCL_GLOBAL_FLAGS carry plain dwords, not
# operands. Other SM4 declarations in this table carry exactly one operand.
DECL_OPERAND_COUNTS = dict.fromkeys(range(88, 92), 1)
DECL_OPERAND_COUNTS.update(dict.fromkeys(range(95, 104), 1))
DECL_OPERAND_COUNTS.update(dict.fromkeys((92, 93, 94, 104, 105, 106), 0))

# Extra plain dwords after each declaration's operand(s): resource dimension,
# semantic id, index range count, temp count, indexable temp layout.
DECL_TRAILING_DWORDS = {
    88: 1, 91: 1, 96: 1, 97: 1, 99: 1, 100: 1, 102: 1, 103: 1,
    104: 1, 105: 3,
}


def _component_text(components):
    return "".join(COMPONENT_NAMES[value] for value in components
                   if 0 <= value < 4)


def decode_operand(words, position, end):
    if position >= end:
        raise ValueError("operand token outside SHDR")
    token = words[position]
    position += 1
    num_components = token & 3
    selection = SELECTION_MODES[(token >> 2) & 3]
    if selection == "mask":
        components = [index for index in range(4) if token & (0x10 << index)]
    elif selection == "swizzle":
        components = [(token >> (4 + index * 2)) & 3 for index in range(4)]
    else:
        components = [(token >> 4) & 3]
    operand_type = (token >> 12) & 0xff
    index_dimension = (token >> 20) & 3
    representations = [(token >> shift) & 3 for shift in (22, 25, 28)]
    extended = bool(token & 0x80000000)

    modifier = "none"
    precision = "default"
    nonuniform = False
    while extended:
        if position >= end:
            raise ValueError("extended operand token outside SHDR")
        extra, = (words[position],)
        position += 1
        if (extra & 0x3f) > 1:
            raise ValueError("unsupported extended operand type %d" %
                             (extra & 0x3f))
        modifier = MODIFIER_NAMES[(extra >> 6) & 3]
        precision = PRECISION_NAMES[(extra >> 14) & 7]
        nonuniform = bool(extra & 0x20000)
        extended = bool(extra & 0x80000000)

    values = []
    if operand_type in (4, 5):
        count = 1 if num_components == 1 else 4
        values = list(words[position:position + count])
        if position + count > end:
            raise ValueError("immediate operand outside SHDR")
        position += count

    indices = []
    for dimension in range(index_dimension):
        representation = INDEX_TYPES[representations[dimension]]
        index = {"kind": representation}
        if representation in ("immediate32", "immediate32_plus_relative"):
            if position >= end:
                raise ValueError("operand index outside SHDR")
            index["value"] = words[position]
            position += 1
        elif representation in ("immediate64", "immediate64_plus_relative"):
            if position + 2 > end:
                raise ValueError("64-bit operand index outside SHDR")
            index["value"] = (words[position] << 32) | words[position + 1]
            position += 2
        if representation in ("relative", "immediate32_plus_relative",
                              "immediate64_plus_relative"):
            relative, position = decode_operand(words, position, end)
            index["operand"] = relative
        indices.append(index)

    result = {
        "type": OPERAND_TYPES[operand_type]
        if operand_type < len(OPERAND_TYPES) else "op_%d" % operand_type,
        "selection": selection,
        "components": _component_text(components),
        "num_components": NUM_COMPONENT_NAMES[num_components],
        "indices": indices,
    }
    if values:
        result["values"] = values
    if modifier != "none":
        result["modifier"] = modifier
    if precision != "default":
        result["precision"] = precision
    if nonuniform:
        result["nonuniform"] = True
    return result, position


def decode_operation(words, position, end):
    start = position
    if position >= end:
        raise ValueError("instruction outside SHDR")
    token = words[position]
    opcode = token & 0x7ff
    if opcode not in OPERAND_COUNTS:
        raise ValueError("no operand count for opcode %d" % opcode)
    length = (token >> 24) & 0x7f
    extended = bool(token & 0x80000000)
    position += 1
    extra_tokens = []
    while extended:
        if position >= end:
            raise ValueError("extended opcode token outside SHDR")
        extra, = (words[position],)
        position += 1
        info = {"type": EXTENDED_OPCODE_TYPES[extra & 3]
                if (extra & 3) < len(EXTENDED_OPCODE_TYPES)
                else "op_%d" % (extra & 0x3f)}
        if (extra & 3) == 1:
            offsets = [(extra >> shift) & 0xf for shift in (9, 13, 17)]
            info["texel_offsets"] = [value - 16 if value > 7 else value
                                     for value in offsets]
        extra_tokens.append(info)
        extended = bool(extra & 0x80000000)
    operands = []
    for _ in range(OPERAND_COUNTS[opcode]):
        operand, position = decode_operand(words, position, end)
        operands.append(operand)
    return {
        "opcode": opcode,
        "name": OPCODE_NAMES[opcode],
        "flags": {
            "saturate": bool(token & 0x2000),
            "nonzero": bool(token & 0x40000),
            "precise": (token >> 19) & 0xf,
        },
        "extended": extra_tokens,
        "operands": operands,
        "consumed": position - start,
    }, position - start


def decode_declaration(words, position, end):
    start = position
    token = words[position]
    opcode = token & 0x7ff
    if opcode not in DECL_OPERAND_COUNTS:
        raise ValueError("no operand count for declaration %d" % opcode)
    position += 1
    operands = []
    for _ in range(DECL_OPERAND_COUNTS[opcode]):
        operand, position = decode_operand(words, position, end)
        operands.append(operand)
    trailing = DECL_TRAILING_DWORDS.get(opcode, 0)
    if position + trailing > end:
        raise ValueError("declaration trailing dwords outside SHDR")
    trailing_words = list(words[position:position + trailing])
    position += trailing
    return {
        "opcode": opcode,
        "name": OPCODE_NAMES[opcode],
        "access_pattern": (token >> 26) & 3 if opcode == 89 else None,
        "operands": operands,
        "trailing": trailing_words,
        "consumed": position - start,
    }, position - start


def parse_shdr(raw, chunk):
    start = chunk["data_offset"]
    end = start + chunk["size"]
    if chunk["size"] < 8:
        raise ValueError("short SHDR chunk")
    version, = struct.unpack_from("<B", raw, start)
    program, = struct.unpack_from("<H", raw, start + 2)
    dword_count, = struct.unpack_from("<I", raw, start + 4)
    words = struct.unpack_from("<%dI" % (chunk["size"] // 4), raw, start)
    position = 2
    opcodes = {}
    instructions = []
    declarations = []
    while position < len(words):
        token = words[position]
        opcode = token & 0x7ff
        length = (token >> 24) & 0x7f
        if length == 0 or position + length > len(words):
            raise ValueError("bad SHDR instruction length 0x%x" % length)
        name = OPCODE_NAMES[opcode] if opcode < len(OPCODE_NAMES) else \
            "OP_%d" % opcode
        opcodes[name] = opcodes.get(name, 0) + 1
        if opcode in DECL_OPERAND_COUNTS:
            item, consumed = decode_declaration(words, position, len(words))
            declarations.append(item)
        else:
            item, consumed = decode_operation(words, position, len(words))
            item["offset"] = position * 4
            instructions.append(item)
        item["length"] = length
        if consumed != length:
            raise ValueError("SHDR %s at +0x%x consumed %d of %d dwords" %
                             (name, position * 4, consumed, length))
        position += length
    return {
        "version": version,
        "shader_type": SHADER_TYPES[program] if program < len(SHADER_TYPES)
                       else hex(program),
        "dword_count": dword_count,
        "instruction_count": len(instructions),
        "declaration_count": len(declarations),
        "opcodes": opcodes,
        "instructions": instructions,
        "declarations": declarations,
    }


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
            elif chunk["tag"] == "SHDR":
                chunk["code"] = parse_shdr(raw, chunk)
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
    code = [chunk["code"] for record in records
            for chunk in record["dxbc"]["chunks"] if chunk["tag"] == "SHDR"]
    instructions = sum(item["instruction_count"] for item in code)
    return "\n".join([
        "%d .nsh files, %d DXBC blobs, %d..%d bytes" %
        (len(shaders), len(records), min(sizes), max(sizes)),
        "chunks: %s" % ", ".join("%s=%d" % item
                                 for item in sorted(chunks.items())),
        "reflection: %s, %d cbuffers, %d variables, %d resources" %
        (", ".join("%s=%d" % item for item in sorted(stages.items())),
         cbuffers, variables, resources),
        "bytecode: %d instructions, %d declarations, %d operands, "
        "version 0x%02x" %
        (instructions,
         sum(item["declaration_count"] for item in code),
         sum(len(op) for item in code for op in item["operands"]),
         min(item["version"] for item in code)),
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
