"""Inventory and extract DXBC bytecode from shipped `NSXR` shader blobs.

    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --report build/tmp/shaders.json --list
    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --extract Body.nsh --stage 0 --out build/tmp/body_dxbc.bin
    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --glsl Copy.nsh --stage 1
    python tools/engine/nsxr_shader.py --dump D:\\Games\\W6W-05 \
        --glsl-dir build/tmp/glsl

`--glsl-dir` also writes `manifest.json` and `bindings.r6glsl`.

`.nsh` files are raw `NSXR` containers. Each has two records; a record points
0x20 bytes ahead of a DirectX bytecode (`DXBC`) blob. SHDR tokens are decoded
into instructions, declarations and SM4 operands (register type, mask/swizzle,
immediate and relative indices, neg/abs modifiers). Structured IF/LOOP/SWITCH
blocks are matched by `control_flow()`; `uniform_usage()` resolves cbuffer
operands against RDEF variables and `resource_usage()` maps texture/sampler
registers to reflected resources. `glsl_es_source()` emits GLSL ES 3.00 with
structured IF/LOOP/SWITCH, integer shadows, relative/array registers and MOVC
using the documented SM4 operand order. No game data is stored in this
repository.
"""

import argparse
import hashlib
import json
import math
import os
import struct

import glsl_manifest

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

# Static GLES coverage for the SM4 opcodes present in the shipped corpus.
# `direct` maps to a GLSL ES 3.00 expression, `lower` needs a small rewrite,
# `control` follows the decoded IF/LOOP/SWITCH blocks and `texture` consumes the
# RDEF resource/sampler bindings. This is opcode coverage, not a GLSL emitter.
SM4_GLSL_ES = {}
for _name, _class, _glsl in (
        ("MOV", "direct", "assign"), ("ADD", "direct", "+"),
        ("MUL", "direct", "*"), ("DIV", "direct", "/"),
        ("MIN", "direct", "min"), ("MAX", "direct", "max"),
        ("SQRT", "direct", "sqrt"), ("RSQ", "direct", "inversesqrt"),
        ("FRC", "direct", "fract"), ("DP2", "direct", "dot(xy)"),
        ("DP3", "direct", "dot(xyz)"), ("DP4", "direct", "dot"),
        ("AND", "direct", "bitwise &"), ("IADD", "direct", "int +"),
        ("IMAX", "direct", "int max"), ("ITOF", "direct", "float()"),
        ("IEQ", "direct", "int equal"), ("ILT", "direct", "int lessThan"),
        ("IGE", "direct", "int greaterThanEqual"),
        ("EQ", "direct", "equal"), ("NE", "direct", "notEqual"),
        ("LT", "direct", "lessThan"), ("GE", "direct", "greaterThanEqual"),
        ("ROUND_Z", "direct", "trunc"), ("DISCARD", "direct", "discard"),
        ("MAD", "lower", "mul + add (no fma in ES 3.00)"),
        ("EXP", "lower", "exp2"), ("LOG", "lower", "log2"),
        ("MOVC", "lower", "conditional select"),
        ("BREAK", "control", "break"), ("CONTINUE", "control", "continue"),
        ("RET", "control", "return"), ("IF", "control", "if"),
        ("ELSE", "control", "else"), ("ENDIF", "control", "endif"),
        ("LOOP", "control", "for"), ("ENDLOOP", "control", "end for"),
        ("BREAKC", "control", "conditional break"),
        ("SWITCH", "control", "switch"), ("CASE", "control", "case"),
        ("DEFAULT", "control", "default"),
        ("ENDSWITCH", "control", "end switch"),
        ("SAMPLE", "texture", "texture(sampler, uv)")):
    SM4_GLSL_ES[_name] = {"class": _class, "glsl": _glsl}

# Subset emitted by glsl_es_source(). Comparison masks are float 0.0/1.0,
# integer register components get an ivec4 shadow, structured control flow
# follows control_flow(), and MOVC follows the documented SM4 operand order:
# https://learn.microsoft.com/windows/win32/direct3dhlsl/movc--sm4---asm-
GLSL_EMIT_BINARY = {"ADD": "+", "MUL": "*", "DIV": "/"}
GLSL_EMIT_DOT = {"DP2": 2, "DP3": 3, "DP4": 4}
GLSL_EMIT_UNARY = {"RSQ": "inversesqrt", "SQRT": "sqrt", "FRC": "fract",
                   "EXP": "exp2", "LOG": "log2", "ROUND_Z": "trunc"}
GLSL_EMIT_COMPARE = {"GE": ">=", "LT": "<", "EQ": "==", "NE": "!="}
GLSL_EMIT_INT_BINARY = {"IADD": "+", "IEQ": "==", "ILT": "<", "IGE": ">="}
GLSL_CONTROL_OPS = {"IF", "ELSE", "ENDIF", "LOOP", "ENDLOOP", "SWITCH",
                    "CASE", "DEFAULT", "ENDSWITCH", "BREAK", "BREAKC",
                    "CONTINUE"}
GLSL_EMIT_OPS = ({"MOV", "MAD", "MIN", "MAX", "SAMPLE", "DISCARD", "RET",
                  "AND", "IMAX", "ITOF", "MOVC"} |
                 set(GLSL_EMIT_BINARY) | set(GLSL_EMIT_DOT) |
                 set(GLSL_EMIT_UNARY) | set(GLSL_EMIT_COMPARE) |
                 set(GLSL_EMIT_INT_BINARY) | GLSL_CONTROL_OPS)

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


def control_flow(instructions):
    """Match structured SM4 control-flow opcodes into nested blocks.

    SM4 shaders in this dump carry no label operands; IF/ELSE/ENDIF,
    LOOP/ENDLOOP and SWITCH/CASE/DEFAULT/ENDSWITCH are matched structurally.
    """
    blocks = []
    stack = []
    unmatched = []
    for index, instruction in enumerate(instructions):
        name = instruction["name"]
        if name in ("IF", "LOOP", "SWITCH"):
            stack.append({"kind": name.lower(), "start": index,
                          "cases": [], "breaks": [], "continues": []})
        elif name == "ELSE" and stack and stack[-1]["kind"] == "if":
            stack[-1]["else"] = index
        elif name in ("CASE", "DEFAULT") and stack and \
                stack[-1]["kind"] == "switch":
            stack[-1]["cases"].append({"kind": name.lower(), "start": index})
        elif name in ("BREAK", "BREAKC"):
            if stack:
                stack[-1]["breaks"].append(index)
            else:
                unmatched.append(index)
        elif name in ("CONTINUE", "CONTINUEC"):
            loop = next((block for block in reversed(stack)
                         if block["kind"] == "loop"), None)
            if loop is None:
                unmatched.append(index)
            else:
                loop["continues"].append(index)
        elif name in ("ENDIF", "ENDLOOP", "ENDSWITCH"):
            if not stack or {"ENDIF": "if", "ENDLOOP": "loop",
                             "ENDSWITCH": "switch"}[name] != stack[-1]["kind"]:
                unmatched.append(index)
                continue
            block = stack.pop()
            block["end"] = index
            blocks.append(block)
    unmatched.extend(block["start"] for block in stack)
    return {"blocks": blocks, "unmatched": unmatched}


COMPONENT_INDEX = {"x": 0, "y": 1, "z": 2, "w": 3}


def uniform_usage(record):
    """Resolve SHDR cbuffer operands to RDEF variables.

    Reflection offsets are bytes; a cbuffer operand selects a 16-byte vector
    plus a component, so scalar variables packed into one vector still resolve.
    """
    reflection = next(chunk["reflection"] for chunk
                      in record["dxbc"]["chunks"] if chunk["tag"] == "RDEF")
    code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                if chunk["tag"] == "SHDR")
    buffers = {item["name"]: item for item in reflection["cbuffers"]}
    bindings = {item["bind_point"]: buffers.get(item["name"])
                for item in reflection["resources"]
                if item["type"] == "cbuffer"}
    usage = {}
    dynamic = 0
    for instruction in code["instructions"]:
        for operand in instruction["operands"]:
            if operand["type"] != "constant_buffer":
                continue
            indices = [index.get("value") for index in operand["indices"][:2]]
            if len(indices) < 2 or any(value is None for value in indices):
                dynamic += 1
                continue
            buffer = bindings.get(indices[0])
            component = COMPONENT_INDEX.get(
                (operand.get("components") or "x")[:1], 0)
            byte = indices[1] * 16 + component * 4
            name = None
            if buffer:
                for variable in buffer["variables"]:
                    if variable["offset"] <= byte < variable["offset"] + \
                            variable["size"]:
                        name = variable["name"]
                        break
            key = "%s.%s" % (buffer["name"] if buffer else "cb%d" % indices[0],
                             name or "?")
            usage[key] = usage.get(key, 0) + 1
    return {"usage": usage, "dynamic": dynamic}


def resource_usage(record):
    """Resolve SHDR texture/sampler registers to RDEF resource names.

    SM4 calls the texture operand type `resource` while RDEF calls the binding
    `texture`; sampler operands and bindings share the name and bind point.
    """
    reflection = next(chunk["reflection"] for chunk
                      in record["dxbc"]["chunks"] if chunk["tag"] == "RDEF")
    code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                if chunk["tag"] == "SHDR")
    bindings = {}
    for item in reflection["resources"]:
        kind = "resource" if item["type"] == "texture" else item["type"]
        if kind in ("resource", "sampler"):
            bindings[(kind, item["bind_point"])] = item["name"]
    declared = set()
    for instruction in code["declarations"]:
        if instruction["name"] not in ("DCL_RESOURCE", "DCL_SAMPLER"):
            continue
        for operand in instruction["operands"]:
            if operand["type"] not in ("resource", "sampler"):
                continue
            index = operand["indices"][0].get("value")
            name = bindings.get((operand["type"], index),
                                "?%s" % index)
            declared.add(operand["type"] + ":" + name)
    usage = {}
    dynamic = unmapped = 0
    for instruction in code["instructions"]:
        for operand in instruction["operands"]:
            if operand["type"] not in ("resource", "sampler"):
                continue
            index = operand["indices"][0].get("value")
            if index is None:
                dynamic += 1
                continue
            name = bindings.get((operand["type"], index))
            if name is None:
                unmapped += 1
                continue
            key = operand["type"] + ":" + name
            usage[key] = usage.get(key, 0) + 1
    return {"usage": usage, "declared": sorted(declared), "dynamic": dynamic,
            "unmapped": unmapped}


def glsl_coverage(data):
    """Count shipped instructions by GLES lowering class."""
    counts = {}
    unknown = {}
    for shader in data["shaders"].values():
        for record in shader["records"]:
            code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                        if chunk["tag"] == "SHDR")
            for instruction in code["instructions"]:
                name = instruction["name"]
                entry = SM4_GLSL_ES.get(name)
                if entry is None:
                    unknown[name] = unknown.get(name, 0) + 1
                    continue
                kind = entry["class"]
                counts[kind] = counts.get(kind, 0) + 1
                counts[name] = counts.get(name, 0) + 1
    total = sum(counts.get(kind, 0) for kind in
                ("direct", "lower", "control", "texture"))
    return {"counts": counts, "unknown": unknown, "total": total}


def _operand_index(operand, position=0):
    return operand["indices"][position].get("value")


def _immediate(raw):
    value, = struct.unpack("<f", struct.pack("<I", raw & 0xffffffff))
    if not math.isfinite(value):
        return "uintBitsToFloat(0x%08xU)" % (raw & 0xffffffff)
    text = "%.9g" % (0.0 if value == 0 else value)
    return text if any(char in text for char in ".eE") else text + ".0"


def _int_components(code):
    """Temp components written or read as integers by integer opcodes."""
    integer = set()

    def add(operand):
        if operand["type"] != "temp":
            return
        index = _operand_index(operand)
        for component in (operand.get("components") or "xyzw"):
            if component in COMPONENT_INDEX:
                integer.add((index, component))

    for instruction in code["instructions"]:
        name = instruction["name"]
        if name in GLSL_EMIT_INT_BINARY or name == "IMAX":
            add(instruction["operands"][0])
        elif name == "ITOF":
            add(instruction["operands"][1])
    # MOV copies integer components without conversion; propagate the type to
    # its destination until stable.
    changed = True
    while changed:
        changed = False
        for instruction in code["instructions"]:
            if instruction["name"] != "MOV":
                continue
            source, target = instruction["operands"][1], instruction["operands"][0]
            if source["type"] != "temp" or target["type"] != "temp":
                continue
            index = _operand_index(source)
            components = source.get("components") or "xyzw"
            if not components or not all((index, item) in integer
                                         for item in components):
                continue
            before = len(integer)
            add(target)
            changed = len(integer) != before
    return integer


def _index_expr(index, context):
    """Render an SM4 immediate or relative register/cbuffer index."""
    if index.get("kind") == "immediate32":
        return str(index["value"])
    if index.get("kind") in ("relative", "immediate32_plus_relative"):
        operand = index["operand"]
        expression = _source(operand, context,
                             _is_int_operand(operand, context))
        expression = "int(%s)" % expression
        if index["kind"] == "immediate32_plus_relative":
            expression = "(%d + %s)" % (index["value"], expression)
        return expression
    raise ValueError("unsupported GLES index %s" % index.get("kind"))


def _is_int_operand(operand, context):
    if operand["type"] != "temp":
        return False
    index = _operand_index(operand)
    components = operand.get("components") or "x"
    return bool(components) and all((index, item) in context["int_components"]
                                    for item in components)


def _source(operand, context, integral=False, component=None):
    kind = operand["type"]
    resolved = False
    if kind == "immediate32":
        values = operand["values"]
        position = COMPONENT_INDEX.get(component, 0)
        raw = values[min(position, len(values) - 1)]
        expr = str(raw if raw < 0x80000000 else raw - 0x100000000) \
            if integral else _immediate(raw)
    elif kind == "resource":
        expr = context["resources"].get(
            _operand_index(operand), "texture%d" % _operand_index(operand))
    elif kind == "sampler":
        expr = "sampler%d" % _operand_index(operand)
    elif kind == "constant_buffer":
        indices = operand["indices"]
        binding = _operand_index(operand)
        name = context["cbuffers"].get(binding, {}).get("name",
                                                        "cb%d" % binding)
        if context.get("ubo") and indices[1].get("kind") == "immediate32":
            expr = _cbuffer_member(binding, indices[1]["value"],
                                   component or operand.get("components") or "x",
                                   context, integral)
            resolved = True
        else:
            expr = "%s[%s]" % (name, _index_expr(indices[1], context))
            if integral:
                expr = "floatBitsToInt(%s)" % expr
    elif kind == "indexable_temp":
        indices = operand["indices"]
        expr = "%s[%s]" % (context["indexable"][_operand_index(operand)],
                           _index_expr(indices[1], context))
        if integral:
            expr = "floatBitsToInt(%s)" % expr
    elif kind in ("temp", "input", "output"):
        prefix = {"temp": "ri" if integral else "r", "input": "in",
                  "output": "out"}[kind]
        expr = "%s%d" % (prefix, _operand_index(operand))
    else:
        raise ValueError("unsupported source operand %s" % kind)
    components = component or operand.get("components")
    if components and kind not in ("immediate32", "resource", "sampler") \
            and not resolved:
        expr += "." + components
    modifier = operand.get("modifier")
    if modifier == "neg":
        return "-(%s)" % expr
    if modifier == "abs":
        return "abs(%s)" % expr
    if modifier == "absneg":
        return "-abs(%s)" % expr
    return expr


def _swizzle_component(operand, position):
    """SM4 POS-swizzle component for destination component `position`."""
    components = operand.get("components") or "xyzw"
    return components[position % len(components)]


def _movc_condition(operand, context, component):
    """SM4 MOVC tests any bit in the condition component (Microsoft SM4 asm)."""
    if operand["type"] == "immediate32":
        return "%s != 0" % _source(operand, context, True, component)
    expression = _source(operand, context, False, component)
    return "floatBitsToInt(%s) != 0" % expression


def _cbuffer_decl(variable):
    """GLSL std140 member for a reflected DXBC cbuffer variable."""
    info = variable["type"]
    name = variable["name"]
    if info["class"] == "scalar" and info["type"] in ("float", "uint") and \
            variable["size"] == 4:
        return {"kind": "scalar", "type": info["type"], "name": name,
                "declaration": "%s %s;" % (info["type"], name)}
    if info["class"] == "vector" and info["type"] == "float" and \
            info["rows"] == 1 and info["cols"] == 4 and \
            variable["size"] == 16:
        return {"kind": "vector", "type": "float", "name": name,
                "declaration": "vec4 %s;" % name}
    if info["class"] == "matrix_rows" and info["type"] == "float" and \
            info["rows"] == 4 and info["cols"] == 4 and \
            variable["size"] == 64:
        return {"kind": "matrix", "type": "float", "name": name,
                "declaration": "vec4 %s[4];" % name}
    return None


def cbuffer_symbols(reflection):
    """Map RDEF cbuffer binds to GLSL names, std140 members and byte regions."""
    buffers = {item["name"]: item for item in reflection["cbuffers"]}
    result = {}
    for resource in reflection["resources"]:
        if resource["type"] != "cbuffer":
            continue
        buffer = buffers.get(resource["name"], {})
        name = "".join(char if char.isalnum() or char == "_" else "_"
                       for char in resource["name"])
        regions = []
        declarations = []
        ubo = True
        for variable in sorted(buffer.get("variables", []),
                               key=lambda item: item["offset"]):
            member = _cbuffer_decl(variable)
            if member is None:
                ubo = False
                continue
            region = dict(member, offset=variable["offset"],
                          size=variable["size"])
            regions.append(region)
            declarations.append(member["declaration"])
        result[resource["bind_point"]] = {
            "name": name,
            "variables": [(item["name"], item["offset"])
                          for item in buffer.get("variables", [])],
            "regions": regions,
            "declarations": declarations,
            "ubo": ubo,
            "size": buffer.get("size", 0),
        }
    return result


def _dynamic_cbuffer(code):
    """True when any cbuffer operand uses a relative or combined index."""
    for instruction in code["instructions"]:
        for operand in instruction["operands"]:
            if operand["type"] != "constant_buffer":
                continue
            index = operand["indices"][1]
            if index.get("kind") != "immediate32":
                return True
    return False


def _cbuffer_member(binding, index, component, context, integral=False):
    """Resolve a static cbuffer vector/component to a named std140 member."""
    byte = index * 16 + COMPONENT_INDEX.get(component, 0) * 4
    info = context["cbuffers"][binding]
    for region in info["regions"]:
        if not region["offset"] <= byte < region["offset"] + region["size"]:
            continue
        name = "%s.%s" % (info["name"], region["name"])
        if region["kind"] == "scalar":
            if region["type"] == "uint":
                return "int(%s)" % name if integral else name
            return "floatBitsToInt(%s)" % name if integral else name
        if region["kind"] == "vector":
            expression = "%s.%s" % (name, component)
        else:
            row = (byte - region["offset"]) // 16
            expression = "%s[%d].%s" % (name, row, component)
        return "floatBitsToInt(%s)" % expression if integral else expression
    raise ValueError("unmapped cbuffer byte %d in bind %d" % (byte, binding))


def glsl_bindings(record):
    """Describe the GLSL interface a host must bind for one DXBC record."""
    code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                if chunk["tag"] == "SHDR")
    reflection = next(chunk["reflection"] for chunk
                      in record["dxbc"]["chunks"] if chunk["tag"] == "RDEF")

    def signature(tag, prefix, skip_system):
        chunk = next(item for item in record["dxbc"]["chunks"]
                     if item["tag"] == tag)
        return sorted(({
            "register": entry["register"],
            "name": "%s%d" % (prefix, entry["register"]),
            "semantic": entry["name"],
            "semantic_index": entry["semantic_index"],
            "mask": entry["mask"],
        } for entry in chunk["signature"]["entries"]
            if not (skip_system and entry["name"].startswith("SV_"))),
            key=lambda item: item["register"])

    slots = {}
    for declaration in code["declarations"]:
        if declaration["name"] == "DCL_CONSTANT_BUFFER":
            operand = declaration["operands"][0]
            slots[_operand_index(operand)] = _operand_index(operand, 1)
    sampler_names = {item["bind_point"]: item["name"]
                     for item in reflection["resources"]
                     if item["type"] == "sampler"}
    symbols = cbuffer_symbols(reflection)
    # ponytail: relative cbuffer indices keep raw named arrays. Add a generated
    # slot selector if a host needs std140 blocks for those four shaders too.
    ubo = not _dynamic_cbuffer(code) and all(
        symbols.get(binding, {}).get("ubo") for binding in slots)
    cbuffers = []
    for binding, count in sorted(slots.items()):
        info = symbols.get(binding, {})
        cbuffers.append({
            "binding": binding,
            "name": info.get("name", "cb%d" % binding),
            "slots": count,
            "size": info.get("size", count * 16),
            "ubo": ubo,
            "regions": [dict(region) for region in info.get("regions", [])],
            "variables": [{"name": name, "offset": offset}
                          for name, offset in info.get("variables", [])],
        })
    textures = sorted(
        ({"binding": item["bind_point"], "name": item["name"]}
         for item in reflection["resources"]
         if item["type"] == "texture"),
        key=lambda item: item["binding"])
    return {
        "stage": reflection["stage"],
        "inputs": signature("ISGN", "in", True),
        "outputs": signature("OSGN", "out", False),
        "cbuffers": cbuffers,
        "textures": textures,
        "samplers": [{"unit": item["binding"], "texture": item["name"],
                      "sampler": sampler_names[item["binding"]]}
                     for item in textures
                     if item["binding"] in sampler_names],
        "ubo": ubo,
    }


def glsl_es_source(record):
    """Emit GLSL ES 3.00 for one DXBC record.

    Supports the decoded structured IF/LOOP/SWITCH blocks, integer register
    components, float comparison masks, indexable temps and MOVC. Static RDEF
    cbuffer accesses become std140 UBO members; records with relative cbuffer
    indices keep named uniform arrays. Output is source text for inspection,
    not driver-validated code.
    """
    code = next(chunk["code"] for chunk in record["dxbc"]["chunks"]
                if chunk["tag"] == "SHDR")
    reflection = next(chunk["reflection"] for chunk
                      in record["dxbc"]["chunks"] if chunk["tag"] == "RDEF")
    unsupported = [ins["name"] for ins in code["instructions"]
                   if ins["name"] not in GLSL_EMIT_OPS]
    if unsupported:
        raise ValueError("unsupported GLES opcodes: %s" %
                         ", ".join(sorted(set(unsupported))))
    flow = control_flow(code["instructions"])
    if flow["unmatched"]:
        raise ValueError("unstructured GLES control flow: %s" %
                         flow["unmatched"])

    layout = glsl_bindings(record)
    indexable = {}
    indexable_counts = {}
    temps = 0
    for declaration in code["declarations"]:
        if declaration["name"] == "DCL_TEMPS":
            temps = max(temps, declaration["trailing"][0])
        elif declaration["name"] == "DCL_INDEXABLE_TEMP":
            register, count, _size = declaration["trailing"]
            indexable[register] = "x%d" % register
            indexable_counts[register] = count
    symbols = {}
    for item in layout["cbuffers"]:
        symbols[item["binding"]] = {
            "name": item["name"],
            "variables": [(variable["name"], variable["offset"])
                          for variable in item["variables"]],
            "regions": item["regions"],
            "declarations": [region["declaration"]
                             for region in item["regions"]],
            "ubo": item["ubo"],
            "size": item["size"],
        }
    ubo_mode = layout["ubo"]
    resources = {item["binding"]: item["name"]
                 for item in layout["textures"]}
    int_components = _int_components(code)
    context = {"resources": resources, "int_components": int_components,
               "indexable": indexable, "cbuffers": symbols, "ubo": ubo_mode}
    for instruction in code["instructions"]:
        for operand in instruction["operands"]:
            if operand["type"] == "temp":
                temps = max(temps, _operand_index(operand) + 1)

    lines = ["#version 300 es", "precision highp float;",
             "precision highp int;"]
    for item in layout["inputs"]:
        lines.append("layout(location=%d) in vec4 %s; // %s" %
                     (item["register"], item["name"], item["semantic"]))
    for item in layout["outputs"]:
        lines.append("layout(location=%d) out vec4 %s; // %s" %
                     (item["register"], item["name"], item["semantic"]))
    for index in range(temps):
        lines.append("vec4 r%d;" % index)
    for index in sorted({index for index, _ in int_components}):
        lines.append("ivec4 ri%d;" % index)
    for register in sorted(indexable):
        lines.append("vec4 x%d[%d];" % (register, indexable_counts[register]))
    for item in layout["cbuffers"]:
        name = item["name"]
        if ubo_mode:
            lines.append("layout(std140) uniform %s_block {" % name)
            for region in item["regions"]:
                lines.append("    " + region["declaration"])
            lines.append("} %s; // cbuffer bind %d, %d bytes" %
                         (name, item["binding"], item["size"]))
        else:
            lines.append("uniform vec4 %s[%d]; // cbuffer bind %d" %
                         (name, item["slots"], item["binding"]))
            for variable in item["variables"]:
                lines.append("//   %s @ byte %d" %
                             (variable["name"], variable["offset"]))
    for item in layout["textures"]:
        lines.append("uniform sampler2D %s; // texture bind %d" %
                     (item["name"], item["binding"]))
    lines.append("void main() {")

    blocks = flow["blocks"]
    opens = {block["start"]: block for block in blocks}
    closes = {block["end"]: block for block in blocks}
    elses = {block["else"]: block for block in blocks if "else" in block}
    cases = {}
    for block in blocks:
        if block["kind"] != "switch":
            continue
        for case in block["cases"]:
            cases[case["start"]] = (block, case)

    def condition(operand):
        integral = _is_int_operand(operand, context)
        expression = _source(operand, context, integral)
        return "%s != 0" % expression if integral else "%s != 0.0" % expression

    def write_result(target, integral, mask, base, expression, indent):
        cast = "ivec4" if integral else "vec4"
        if mask == "xyzw":
            lines.append("%s%s = %s(%s);" % (indent, base, cast, expression))
        else:
            lines.append("%s%s.%s = %s(%s).%s;" %
                         (indent, base, mask, cast, expression, mask))
        if target["type"] != "temp":
            return
        index = _operand_index(target)
        if integral:
            lines.append("%sr%d.%s = %s(intBitsToFloat(ri%d.%s)).%s;" %
                         (indent, index, mask, "vec4", index, mask, mask))
        else:
            for component in mask:
                if (index, component) in int_components:
                    lines.append(
                        "%sri%d.%s = ivec4(floatBitsToInt(r%d.%s)).%s;" %
                        (indent, index, component, index, component,
                         component))

    level = 1
    active_case = {}
    for index, instruction in enumerate(code["instructions"]):
        name = instruction["name"]
        operands = instruction["operands"]
        indent = "    " * level

        if index in closes:
            level -= 1
            active_case.pop(closes[index]["start"], None)
            lines.append("    " * level + "}")
            continue
        if index in elses:
            lines.append("    " * (level - 1) + "} else {")
            continue
        if index in cases:
            block, case = cases[index]
            if block["start"] in active_case:
                level -= 1
            label = "default:" if case["kind"] == "default" else \
                "case %d:" % operands[0]["values"][0]
            lines.append("    " * (level - 1) + label)
            level += 1
            active_case[block["start"]] = index
            continue
        if index in opens:
            block = opens[index]
            if block["kind"] == "loop":
                header = "for (;;) {"
            elif block["kind"] == "if":
                header = "if (%s) {" % condition(operands[0])
            else:
                selector = operands[0]
                integral = selector["type"] != "constant_buffer"
                expression = _source(selector, context, integral)
                header = "switch (%s%s) {" % (
                    "" if integral else "int(",
                    expression if integral else expression + ")")
            lines.append(indent + header)
            level += 1
            continue
        if name == "BREAK":
            lines.append(indent + "break;")
            continue
        if name == "BREAKC":
            lines.append(indent + "if (%s) break;" % condition(operands[0]))
            continue
        if name == "CONTINUE":
            lines.append(indent + "continue;")
            continue
        if name in GLSL_CONTROL_OPS or name == "CASE" or name == "DEFAULT":
            continue

        if name == "RET":
            lines.append(indent + "return;")
            continue
        if name == "DISCARD":
            lines.append(indent + "discard;")
            continue

        target = operands[0]
        if target["type"] not in ("temp", "output", "indexable_temp"):
            raise ValueError("unsupported GLES target %s" % target["type"])
        integral = _is_int_operand(target, context)
        integral_source = integral or name in GLSL_EMIT_INT_BINARY or \
            name in ("IMAX", "ITOF")

        def source_integral(item):
            if item["type"] in ("temp", "indexable_temp"):
                return _is_int_operand(item, context)
            if item["type"] == "constant_buffer":
                return integral_source
            return integral and item["type"] == "immediate32"

        args = [_source(item, context, source_integral(item))
                for item in operands[1:]]
        if name == "MOVC":
            if target["type"] == "indexable_temp":
                movc_base = "%s[%s]" % (
                    indexable[_operand_index(target)],
                    _index_expr(target["indices"][1], context))
            else:
                movc_base = "%s%d" % (
                    {"temp": "ri" if integral else "r",
                     "output": "out"}[target["type"]],
                    _operand_index(target))
            mask = target.get("components") or "xyzw"
            for position, component in enumerate(mask):
                condition_component = _swizzle_component(operands[1], position)
                true_component = _swizzle_component(operands[2], position)
                false_component = _swizzle_component(operands[3], position)
                test = _movc_condition(operands[1], context,
                                       condition_component)
                true_value = _source(operands[2], context, integral,
                                     true_component)
                false_value = _source(operands[3], context, integral,
                                      false_component)
                write_result(target, integral, component, movc_base,
                             "(%s ? %s : %s)" % (test, true_value,
                                                 false_value), indent)
            continue
        if name == "MOV":
            if integral and not source_integral(operands[1]):
                expression = "floatBitsToInt(%s)" % args[0]
            elif not integral and source_integral(operands[1]):
                expression = "intBitsToFloat(%s)" % args[0]
            else:
                expression = args[0]
        elif name == "ITOF":
            expression = args[0]
        elif name in GLSL_EMIT_BINARY:
            expression = "(%s %s %s)" % (args[0], GLSL_EMIT_BINARY[name],
                                         args[1])
        elif name == "MIN" or name == "MAX":
            expression = "%s(%s, %s)" % (name.lower(), args[0], args[1])
        elif name == "MAD":
            expression = "(%s * %s + %s)" % tuple(args[:3])
        elif name in GLSL_EMIT_COMPARE:
            expression = "(%s %s %s)" % (args[0], GLSL_EMIT_COMPARE[name],
                                         args[1])
        elif name == "AND":
            expression = "min(%s, %s)" % (args[0], args[1])
        elif name in GLSL_EMIT_INT_BINARY:
            expression = "(%s %s %s)" % (args[0], GLSL_EMIT_INT_BINARY[name],
                                         args[1])
        elif name == "IMAX":
            expression = "max(%s, %s)" % (args[0], args[1])
        elif name in GLSL_EMIT_DOT:
            width = GLSL_EMIT_DOT[name]
            expression = "dot(vec%d(%s), vec%d(%s))" % (
                width, args[0], width, args[1])
        elif name in GLSL_EMIT_UNARY:
            expression = "%s(%s)" % (GLSL_EMIT_UNARY[name], args[0])
        elif name == "SAMPLE":
            expression = "texture(%s, vec2(%s))" % (
                context["resources"].get(
                    _operand_index(operands[2]), "texture%d" %
                    _operand_index(operands[2])), args[0])
        else:
            raise ValueError("unsupported GLES opcode %s" % name)
        if not integral and instruction["flags"]["saturate"]:
            expression = "clamp(%s, 0.0, 1.0)" % expression
        if target["type"] == "indexable_temp":
            base = "%s[%s]" % (indexable[_operand_index(target)],
                               _index_expr(target["indices"][1], context))
        else:
            base = "%s%d" % ({"temp": "ri" if integral else "r",
                              "output": "out"}[target["type"]],
                             _operand_index(target))
        mask = target.get("components") or "xyzw"
        write_result(target, integral, mask, base, expression, indent)
    lines.append("}")
    return "\n".join(lines) + "\n"


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


def export_glsl(data, directory):
    """Write emitted GLSL for every record; return a deterministic manifest."""
    os.makedirs(directory, exist_ok=True)
    manifest = []
    for name, shader in sorted(data["shaders"].items()):
        stem = os.path.splitext(name)[0]
        for record in shader["records"]:
            source = glsl_es_source(record)
            encoded = source.encode("utf8")
            relative = "%s.stage%d.glsl" % (stem, record["index"])
            with open(os.path.join(directory, relative), "w", encoding="utf8",
                      newline="\n") as stream:
                stream.write(source)
            reflection = next(chunk["reflection"] for chunk
                              in record["dxbc"]["chunks"]
                              if chunk["tag"] == "RDEF")
            manifest.append({
                "shader": name,
                "stage": record["index"],
                "stage_kind": reflection["stage"],
                "file": relative,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "bindings": glsl_bindings(record),
            })
    manifest.sort(key=lambda item: (item["shader"], item["stage"]))
    with open(os.path.join(directory, "manifest.json"), "w",
              encoding="utf8") as stream:
        json.dump({"count": len(manifest), "shaders": manifest}, stream,
                  indent=2, ensure_ascii=False)
    with open(os.path.join(directory, "bindings.r6glsl"), "wb") as stream:
        stream.write(glsl_manifest.build({"shaders": manifest}))
    return manifest


def report_text(data):
    shaders = data["shaders"]
    coverage = glsl_coverage(data)
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
         sum(len(ins["operands"]) for item in code
             for ins in item["instructions"]),
         min(item["version"] for item in code)),
        "GLES coverage: %d/%d instructions, unknown %d" %
        (coverage["total"], instructions, sum(coverage["unknown"].values())),
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extract")
    parser.add_argument("--glsl")
    parser.add_argument("--glsl-dir")
    parser.add_argument("--stage", type=int, default=0)
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.glsl_dir:
        manifest = export_glsl(collect(args.dump), args.glsl_dir)
        print("exported %d GLSL ES records to %s" %
              (len(manifest), args.glsl_dir))
        return 0

    if args.glsl:
        header = parse_nsh(os.path.join(args.dump, SHADER_DIR, args.glsl))
        if not 0 <= args.stage < header["record_count"]:
            raise ValueError("stage %d outside %s" %
                             (args.stage, args.glsl))
        source = glsl_es_source(header["records"][args.stage])
        if args.out:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)),
                        exist_ok=True)
            with open(args.out, "w", encoding="utf8") as stream:
                stream.write(source)
        else:
            print(source, end="")
        return 0

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
