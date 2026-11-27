"""Check the C structured SM4 control-flow reader against shipped SHDR code."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import shader_control_flow_catalog as catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80
NO_ELSE = 0xFFFFFFFF


class Header(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "version", "record_count", "block_count", "case_count",
        "index_count", "records_off", "blocks_off", "cases_off",
        "indices_off", "strings_off", "strings_size")]


class Record(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "name_off", "stage", "first_block", "block_count",
        "unmatched_first", "unmatched_count")]


class Block(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "kind", "start", "end", "else_index", "case_first", "case_count",
        "break_first", "break_count", "continue_first", "continue_count")]


class Case(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_uint32), ("start", ctypes.c_uint32)]


def expected_tables(rows, header):
    case_base = header.cases_off // catalog.CASE.size
    index_base = header.indices_off // catalog.INDEX.size
    blocks = []
    cases = []
    indices = []
    records = []
    for row in rows:
        unmatched_first = len(indices)
        indices.extend(row["unmatched"])
        first_block = len(blocks)
        for block in row["blocks"]:
            case_first = len(cases)
            for case in block["cases"]:
                cases.append((catalog.CASE_KIND[case["kind"]], case["start"]))
            break_first = len(indices)
            indices.extend(block["breaks"])
            continue_first = len(indices)
            indices.extend(block["continues"])
            blocks.append((
                catalog.KIND[block["kind"]], block["start"], block["end"],
                block.get("else", NO_ELSE), case_base + case_first,
                len(block["cases"]), index_base + break_first,
                len(block["breaks"]), index_base + continue_first,
                len(block["continues"])))
        records.append((row["name"], row["stage"], first_block,
                        len(row["blocks"]), index_base + unmatched_first,
                        len(row["unmatched"])))
    return records, blocks, cases, indices


def configure(lib):
    lib.r6_shader_cf_parse.restype = ctypes.c_int
    lib.r6_shader_cf_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_shader_cf_record.restype = ctypes.c_int
    lib.r6_shader_cf_record.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_uint32,
                                        ctypes.POINTER(Record)]
    lib.r6_shader_cf_name.restype = ctypes.c_int
    lib.r6_shader_cf_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.c_char_p,
                                      ctypes.c_size_t]
    lib.r6_shader_cf_find.restype = ctypes.c_int
    lib.r6_shader_cf_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_char_p, ctypes.c_uint32,
                                      ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_shader_cf_block.restype = ctypes.c_int
    lib.r6_shader_cf_block.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32,
                                       ctypes.POINTER(Block)]
    lib.r6_shader_cf_case.restype = ctypes.c_int
    lib.r6_shader_cf_case.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.POINTER(Case)]
    lib.r6_shader_cf_index.restype = ctypes.c_int
    lib.r6_shader_cf_index.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.c_uint32)]


def check(dump, lib):
    configure(lib)
    rows, unmatched = catalog.collect(dump)
    blob = catalog.build(rows, unmatched)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_shader_cf_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK

    want_records, want_blocks, want_cases, want_indices = expected_tables(
        rows, header)
    assert (header.record_count, header.block_count, header.case_count,
            header.index_count) == (446, 303, 2448, 2478)
    assert not unmatched

    record = Record()
    block = Block()
    case = Case()
    value = ctypes.c_uint32()
    name = ctypes.create_string_buffer(NAME_CAP)
    for index, expected in enumerate(want_records):
        assert lib.r6_shader_cf_record(source, len(blob), index,
                                       ctypes.byref(record)) == R6_OK
        assert (record.stage, record.first_block, record.block_count,
                record.unmatched_first,
                record.unmatched_count) == expected[1:]
        assert lib.r6_shader_cf_name(source, len(blob), index, name,
                                     len(name)) == R6_OK
        assert name.value.decode("utf8") == expected[0]
        assert lib.r6_shader_cf_find(
            source, len(blob), expected[0].encode("utf8"), expected[1],
            ctypes.byref(value)) == R6_OK
        assert value.value == index

    for index, expected in enumerate(want_blocks):
        assert lib.r6_shader_cf_block(source, len(blob), index,
                                      ctypes.byref(block)) == R6_OK
        assert tuple(getattr(block, field) for field in (
            "kind", "start", "end", "else_index", "case_first", "case_count",
            "break_first", "break_count", "continue_first",
            "continue_count")) == expected
    for index, expected in enumerate(want_cases):
        assert lib.r6_shader_cf_case(source, len(blob), index,
                                     ctypes.byref(case)) == R6_OK
        assert (case.kind, case.start) == expected
    for index, expected in enumerate(want_indices):
        assert lib.r6_shader_cf_index(source, len(blob), index,
                                      ctypes.byref(value)) == R6_OK
        assert value.value == expected

    body = want_records[[row[0] for row in want_records].index("Body.nsh")]
    assert body[1] == 0
    pixel_index = [row[0] for row in want_records].index("Body.nsh") + 1
    assert lib.r6_shader_cf_record(source, len(blob), pixel_index,
                                   ctypes.byref(record)) == R6_OK
    switches = []
    for index in range(record.first_block,
                       record.first_block + record.block_count):
        assert lib.r6_shader_cf_block(source, len(blob), index,
                                      ctypes.byref(block)) == R6_OK
        if block.kind == catalog.KIND["switch"]:
            switches.append((block.start, block.end, block.case_count,
                             block.break_count))
    assert switches == [(66, 104, 9, 9), (106, 144, 9, 9)]

    assert lib.r6_shader_cf_find(
        source, len(blob), b"Body.nsh", 2,
        ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_shader_cf_find(
        source, len(blob), b"R6_NO_SUCH_SHADER", 0,
        ctypes.byref(value)) == R6_ERR_NOT_FOUND
    assert lib.r6_shader_cf_find(
        source, len(blob), b"", 0,
        ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_shader_cf_record(source, len(blob), 446,
                                   ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_shader_cf_block(source, len(blob), 303,
                                  ctypes.byref(block)) == R6_ERR_ARG
    assert lib.r6_shader_cf_case(source, len(blob), 2448,
                                 ctypes.byref(case)) == R6_ERR_ARG
    assert lib.r6_shader_cf_index(source, len(blob), 2478,
                                  ctypes.byref(value)) == R6_ERR_ARG
    assert lib.r6_shader_cf_name(source, len(blob), 0, name,
                                 4) == R6_ERR_BUFFER
    assert lib.r6_shader_cf_record(source, len(blob), 0,
                                   None) == R6_ERR_ARG

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_cf_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 8, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_cf_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 36, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_cf_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_shader_cf_parse(source, len(bad) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT

    print("SM4 control flow: 446 records, 303 blocks, 2448 cases, 2478 "
          "indices and all names match nsxr_shader.control_flow(); Body.nsh "
          "pixel has two 9-case switches; bad blob, index, stage and "
          "capacity rejected")


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
