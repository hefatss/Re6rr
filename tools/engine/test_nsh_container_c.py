"""Check the C NSXR/DXBC container reader against all shipped .nsh files."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nsxr_shader  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7

REFLECTION_NAMES = [
    "record_count", "vertex_count", "pixel_count", "target_version", "flags",
    "cbuffer_count", "cbuffer_bytes", "variable_count", "resource_count",
    "resource_cbuffer", "resource_texture", "resource_sampler",
    "class_scalar", "class_vector", "class_matrix_rows", "type_float",
    "type_uint", "nonzero_member_offsets", "dimension_0", "dimension_4",
    "dimension_9", "sample_count_0", "sample_count_all",
]
CREATOR = "Microsoft (R) HLSL Shader Compiler 9.29.952.3111"


class Chunk(ctypes.Structure):
    _fields_ = [("tag", ctypes.c_uint32), ("offset", ctypes.c_uint32),
                ("size", ctypes.c_uint32),
                ("data_offset", ctypes.c_uint32)]


class Record(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32), ("count", ctypes.c_uint32),
                ("dxbc_size", ctypes.c_uint32),
                ("reserved", ctypes.c_uint32),
                ("dxbc_offset", ctypes.c_uint32),
                ("dxbc_version", ctypes.c_uint32),
                ("dxbc_actual_size", ctypes.c_uint32),
                ("chunk_count", ctypes.c_uint32),
                ("digest", ctypes.c_uint8 * 16),
                ("chunks", Chunk * 8)]


class Nsh(ctypes.Structure):
    _fields_ = [("file_size", ctypes.c_uint32),
                ("version", ctypes.c_uint32),
                ("subversion", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("record_count", ctypes.c_uint32),
                ("table", ctypes.c_uint32 * 5),
                ("records", Record * 2)]


class StatFacts(ctypes.Structure):
    _fields_ = [("record_count", ctypes.c_uint32)] + [
        (name, ctypes.c_uint32) for name in nsxr_shader.STAT_FIELDS[:29]]


class ReflectionFacts(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in REFLECTION_NAMES]


def check(dump, lib):
    lib.r6_nsh_parse.restype = ctypes.c_int
    lib.r6_nsh_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(Nsh)]
    lib.r6_nsh_chunk_find.restype = ctypes.c_int
    lib.r6_nsh_chunk_find.argtypes = [ctypes.POINTER(Nsh), ctypes.c_uint32,
                                      ctypes.c_uint32, ctypes.POINTER(Chunk)]
    lib.r6_dxbc_stat_facts.restype = None
    lib.r6_dxbc_stat_facts.argtypes = [ctypes.POINTER(StatFacts)]
    lib.r6_dxbc_reflection_facts.restype = None
    lib.r6_dxbc_reflection_facts.argtypes = [ctypes.POINTER(ReflectionFacts)]
    lib.r6_dxbc_reflection_creator.restype = ctypes.c_int
    lib.r6_dxbc_reflection_creator.argtypes = [ctypes.c_char_p,
                                               ctypes.c_size_t]
    root = os.path.join(dump, nsxr_shader.SHADER_DIR)
    names = sorted(name for name in os.listdir(root) if name.endswith(".nsh"))
    assert len(names) == 223
    chunks = 0
    stat_records = 0
    totals = {name: 0 for name in nsxr_shader.STAT_FIELDS[:29]}
    reflection = {name: 0 for name in REFLECTION_NAMES}
    creators = set()
    for name in names:
        with open(os.path.join(root, name), "rb") as stream:
            raw = stream.read()
        want = nsxr_shader.parse_nsh(os.path.join(root, name))
        source = ctypes.create_string_buffer(raw, len(raw))
        got = Nsh()
        assert lib.r6_nsh_parse(source, len(raw), ctypes.byref(got)) == R6_OK, \
            name
        assert got.file_size == want["size"], name
        assert got.version == want["version"], name
        assert got.subversion == want["subversion"], name
        assert got.flags == want["flags"], name
        assert got.record_count == want["record_count"], name
        assert tuple(got.table) == tuple(want["table"]), name
        for index, record in enumerate(want["records"]):
            item = got.records[index]
            assert item.offset == record["offset"], (name, index, "offset")
            assert item.count == record["count"], (name, index, "count")
            assert item.dxbc_size == record["dxbc_size"], (name, index)
            assert item.reserved == record["reserved"], (name, index)
            blob = record["dxbc"]
            assert item.dxbc_offset == blob["raw_offset"], (name, index)
            assert item.dxbc_version == blob["version"], (name, index)
            assert item.dxbc_actual_size == blob["size"], (name, index)
            assert item.chunk_count == len(blob["chunks"]), (name, index)
            assert bytes(item.digest) == bytes.fromhex(blob["digest"]), \
                (name, index, "digest")
            for part_index, part in enumerate(blob["chunks"]):
                cpart = item.chunks[part_index]
                tag, = struct.unpack("<I", part["tag"].encode("ascii"))
                assert cpart.tag == tag, (name, index, part_index, "tag")
                assert cpart.offset == part["offset"], (name, index)
                assert cpart.size == part["size"], (name, index)
                assert cpart.data_offset == part["data_offset"], (name, index)
                if part["tag"] == "STAT":
                    stats = part["statistics"]
                    assert len(stats) == len(totals), (name, index)
                    stat_records += 1
                    for field in totals:
                        totals[field] += stats[field]
                elif part["tag"] == "RDEF":
                    data = part["reflection"]
                    creators.add(data["creator"])
                    if not reflection["record_count"]:
                        reflection["target_version"] = data["target_version"]
                        reflection["flags"] = data["flags"]
                    else:
                        assert reflection["target_version"] == \
                            data["target_version"], (name, index)
                        assert reflection["flags"] == data["flags"], \
                            (name, index)
                    reflection["record_count"] += 1
                    reflection["vertex_count"] += data["stage"] == "vertex"
                    reflection["pixel_count"] += data["stage"] == "pixel"
                    reflection["cbuffer_count"] += len(data["cbuffers"])
                    reflection["cbuffer_bytes"] += sum(
                        block["size"] for block in data["cbuffers"])
                    variables = [variable
                                 for block in data["cbuffers"]
                                 for variable in block["variables"]]
                    resources = data["resources"]
                    reflection["variable_count"] += len(variables)
                    reflection["resource_count"] += len(resources)
                    reflection["resource_cbuffer"] += sum(
                        item["type"] == "cbuffer" for item in resources)
                    reflection["resource_texture"] += sum(
                        item["type"] == "texture" for item in resources)
                    reflection["resource_sampler"] += sum(
                        item["type"] == "sampler" for item in resources)
                    reflection["class_scalar"] += sum(
                        item["type"]["class"] == "scalar"
                        for item in variables)
                    reflection["class_vector"] += sum(
                        item["type"]["class"] == "vector"
                        for item in variables)
                    reflection["class_matrix_rows"] += sum(
                        item["type"]["class"] == "matrix_rows"
                        for item in variables)
                    reflection["type_float"] += sum(
                        item["type"]["type"] == "float" for item in variables)
                    reflection["type_uint"] += sum(
                        item["type"]["type"] == "uint" for item in variables)
                    reflection["nonzero_member_offsets"] += sum(
                        bool(item["type"]["member_offset"])
                        for item in variables)
                    reflection["dimension_0"] += sum(
                        item["dimension"] == 0 for item in resources)
                    reflection["dimension_4"] += sum(
                        item["dimension"] == 4 for item in resources)
                    reflection["dimension_9"] += sum(
                        item["dimension"] == 9 for item in resources)
                    reflection["sample_count_0"] += sum(
                        item["sample_count"] == 0 for item in resources)
                    reflection["sample_count_all"] += sum(
                        item["sample_count"] == 0xFFFFFFFF
                        for item in resources)
                chunks += 1

    first_raw = open(os.path.join(root, names[0]), "rb").read()
    source = ctypes.create_string_buffer(first_raw, len(first_raw))
    got = Nsh()
    assert lib.r6_nsh_parse(source, len(first_raw), ctypes.byref(got)) == R6_OK
    found = Chunk()
    for record_index in range(got.record_count):
        if not got.records[record_index].chunk_count:
            continue
        expected = got.records[record_index].chunks[0]
        assert lib.r6_nsh_chunk_find(
            ctypes.byref(got), record_index, expected.tag,
            ctypes.byref(found)) == R6_OK
        assert found.tag == expected.tag
        assert found.offset == expected.offset
        assert found.size == expected.size
        assert found.data_offset == expected.data_offset
    assert lib.r6_nsh_chunk_find(
        ctypes.byref(got), 0, 0, ctypes.byref(found)) == R6_ERR_NOT_FOUND
    assert lib.r6_nsh_chunk_find(
        ctypes.byref(got), 2, 0, ctypes.byref(found)) == R6_ERR_ARG

    header = Nsh()
    assert lib.r6_nsh_parse(None, 0x80, ctypes.byref(header)) == R6_ERR_ARG
    assert lib.r6_nsh_parse(bytes(0x7F), 0x7F,
                            ctypes.byref(header)) == R6_ERR_ARG
    bad = bytes(0x80)
    source = ctypes.create_string_buffer(bad, len(bad))
    assert lib.r6_nsh_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_ARG
    good = open(os.path.join(root, names[0]), "rb").read()
    bad = bytearray(good)
    struct.pack_into("<I", bad, 4, len(bad) + 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nsh_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(good)
    struct.pack_into("<I", bad, 0x80, len(bad))
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nsh_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT

    assert stat_records == 446
    facts = StatFacts()
    lib.r6_dxbc_stat_facts(ctypes.byref(facts))
    assert facts.record_count == stat_records
    for field in totals:
        assert getattr(facts, field) == totals[field], (
            field, getattr(facts, field), totals[field])
    lib.r6_dxbc_stat_facts(None)

    assert reflection["record_count"] == 446
    assert creators == {CREATOR}
    assert (reflection["class_scalar"] + reflection["class_vector"] +
            reflection["class_matrix_rows"]) == reflection["variable_count"]
    assert (reflection["type_float"] + reflection["type_uint"] ==
            reflection["variable_count"])
    assert (reflection["dimension_0"] + reflection["dimension_4"] +
            reflection["dimension_9"]) == reflection["resource_count"]
    assert (reflection["sample_count_0"] +
            reflection["sample_count_all"]) == reflection["resource_count"]
    reflected = ReflectionFacts()
    lib.r6_dxbc_reflection_facts(ctypes.byref(reflected))
    for field in REFLECTION_NAMES:
        assert getattr(reflected, field) == reflection[field], (
            field, getattr(reflected, field), reflection[field])
    lib.r6_dxbc_reflection_facts(None)

    creator = ctypes.create_string_buffer(0x40)
    assert lib.r6_dxbc_reflection_creator(
        creator, len(creator)) == R6_OK
    assert creator.value.decode("ascii") == CREATOR
    assert lib.r6_dxbc_reflection_creator(creator, 1) == R6_ERR_BUFFER
    assert lib.r6_dxbc_reflection_creator(None, len(creator)) == R6_ERR_ARG
    assert lib.r6_dxbc_reflection_creator(creator, 0) == R6_ERR_ARG
    print("NSXR: %d files, 2 records each, %d DXBC chunks, all 29 summed "
          "STAT fields and all 23 summed RDEF fields match "
          "nsxr_shader.parse_nsh(); the one creator string and bad capacities "
          "are checked, as are chunk find, short input, bad magic and bad "
          "sizes" % (len(names), chunks))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(args.dump, lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
