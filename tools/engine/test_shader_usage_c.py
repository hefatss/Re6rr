"""Check the C shader usage reader against shipped SHDR/RDEF resolution."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import shader_usage_catalog as catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "version", "record_count", "uniform_count", "resource_count",
        "declared_count", "record_off", "uniform_off", "resource_off",
        "declared_off", "strings_off", "strings_size")]


class Record(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "name_off", "stage", "uniform_first", "uniform_count",
        "dynamic_cbuffer", "resource_first", "resource_count",
        "declared_first", "declared_count", "dynamic_resource",
        "unmapped_resource")]


def configure(lib):
    lib.r6_shader_usage_parse.restype = ctypes.c_int
    lib.r6_shader_usage_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_shader_usage_record.restype = ctypes.c_int
    lib.r6_shader_usage_record.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_uint32,
                                           ctypes.POINTER(Record)]
    lib.r6_shader_usage_name.restype = ctypes.c_int
    lib.r6_shader_usage_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_uint32, ctypes.c_char_p,
                                         ctypes.c_size_t]
    lib.r6_shader_usage_find.restype = ctypes.c_int
    lib.r6_shader_usage_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_char_p, ctypes.c_uint32,
                                         ctypes.POINTER(ctypes.c_uint32)]
    for getter in ("uniform", "resource"):
        function = getattr(lib, "r6_shader_usage_" + getter)
        function.restype = ctypes.c_int
        function.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                             ctypes.c_uint32, ctypes.c_uint32,
                             ctypes.c_char_p, ctypes.c_size_t,
                             ctypes.POINTER(ctypes.c_uint32)]
    for finder in ("find_uniform", "find_resource"):
        function = getattr(lib, "r6_shader_usage_" + finder)
        function.restype = ctypes.c_int
        function.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                             ctypes.c_uint32, ctypes.c_char_p,
                             ctypes.POINTER(ctypes.c_uint32),
                             ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_shader_usage_declared.restype = ctypes.c_int
    lib.r6_shader_usage_declared.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.c_uint32, ctypes.c_uint32,
                                             ctypes.c_char_p, ctypes.c_size_t]


def check(dump, lib):
    configure(lib)
    rows = catalog.collect(dump)
    blob = catalog.build(rows)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_shader_usage_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert (header.record_count, header.uniform_count,
            header.resource_count, header.declared_count) == (446, 1645,
                                                              1052, 1052)
    assert sum(sum(row["uniforms"].values()) for row in rows) == 5502
    assert sum(row["dynamic_cbuffer"] for row in rows) == 8
    assert sum(sum(row["resources"].values()) for row in rows) == 1360
    assert sum(row["dynamic_resource"] for row in rows) == 0
    assert sum(row["unmapped_resource"] for row in rows) == 0
    assert len({key for row in rows for key in row["uniforms"]}) == 63
    assert len({key for row in rows for key in row["resources"]}) == 27

    record = Record()
    name = ctypes.create_string_buffer(NAME_CAP)
    found_name = ctypes.create_string_buffer(NAME_CAP)
    row_index = ctypes.c_uint32()
    count = ctypes.c_uint32()
    uniform_first = 0
    resource_first = 0
    declared_first = 0
    for index, row in enumerate(rows):
        assert lib.r6_shader_usage_record(source, len(blob), index,
                                          ctypes.byref(record)) == R6_OK
        assert (record.stage, record.uniform_first, record.uniform_count,
                record.dynamic_cbuffer, record.resource_first,
                record.resource_count, record.declared_first,
                record.declared_count, record.dynamic_resource,
                record.unmapped_resource) == (
            row["stage"], uniform_first, len(row["uniforms"]),
            row["dynamic_cbuffer"], resource_first, len(row["resources"]),
            declared_first, len(row["declared"]), row["dynamic_resource"],
            row["unmapped_resource"])
        assert lib.r6_shader_usage_name(source, len(blob), index, name,
                                        len(name)) == R6_OK
        assert name.value.decode("utf8") == row["name"]
        assert lib.r6_shader_usage_find(
            source, len(blob), row["name"].encode("utf8"), row["stage"],
            ctypes.byref(row_index)) == R6_OK
        assert row_index.value == index
        uniform_first += len(row["uniforms"])
        resource_first += len(row["resources"])
        declared_first += len(row["declared"])

        for position, expected in enumerate(sorted(row["uniforms"].items())):
            assert lib.r6_shader_usage_uniform(
                source, len(blob), index, position, name, len(name),
                ctypes.byref(count)) == R6_OK
            assert name.value.decode("utf8") == expected[0]
            assert count.value == expected[1]
            assert lib.r6_shader_usage_find_uniform(
                source, len(blob), index, expected[0].encode("utf8"),
                ctypes.byref(row_index), ctypes.byref(count)) == R6_OK
            assert row_index.value == position and count.value == expected[1]
        for position, expected in enumerate(sorted(row["resources"].items())):
            assert lib.r6_shader_usage_resource(
                source, len(blob), index, position, name, len(name),
                ctypes.byref(count)) == R6_OK
            assert name.value.decode("utf8") == expected[0]
            assert count.value == expected[1]
            assert lib.r6_shader_usage_find_resource(
                source, len(blob), index, expected[0].encode("utf8"),
                ctypes.byref(row_index), ctypes.byref(count)) == R6_OK
            assert row_index.value == position and count.value == expected[1]
        for position, expected in enumerate(row["declared"]):
            assert lib.r6_shader_usage_declared(
                source, len(blob), index, position, found_name,
                len(found_name)) == R6_OK
            assert found_name.value.decode("utf8") == expected

    body_pixel = next(index for index, row in enumerate(rows)
                      if row["name"] == "Body.nsh" and row["stage"] == 1)
    assert "AlphaTest.AlphaTestRef" in rows[body_pixel]["uniforms"]
    assert "AlphaTest.AlphaTestFunc" in rows[body_pixel]["uniforms"]
    assert sum(key.startswith("resource:") for key in
               rows[body_pixel]["resources"]) == 3
    assert sum(key.startswith("sampler:") for key in
               rows[body_pixel]["resources"]) == 3

    assert lib.r6_shader_usage_find(
        source, len(blob), b"Body.nsh", 2,
        ctypes.byref(row_index)) == R6_ERR_ARG
    assert lib.r6_shader_usage_find(
        source, len(blob), b"R6_NO_SUCH_SHADER", 0,
        ctypes.byref(row_index)) == R6_ERR_NOT_FOUND
    assert lib.r6_shader_usage_uniform(source, len(blob), 0, 1645, name,
                                       len(name),
                                       ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_shader_usage_uniform(source, len(blob), 0, 0, name, 4,
                                       ctypes.byref(count)) == R6_ERR_BUFFER
    assert lib.r6_shader_usage_find_uniform(
        source, len(blob), 0, b"R6_NO_SUCH_UNIFORM", ctypes.byref(row_index),
        ctypes.byref(count)) == R6_ERR_NOT_FOUND
    assert lib.r6_shader_usage_record(source, len(blob), 446,
                                      ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_shader_usage_declared(source, len(blob), 0, 1052, name,
                                        len(name)) == R6_ERR_ARG

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_usage_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 36, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_shader_usage_parse(source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_shader_usage_parse(source, len(bad) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT

    print("SHDR usage: 446 records, 1645 uniform rows, 1052 resource rows and "
          "1052 declarations match nsxr_shader; 5502 static cbuffer operands, "
          "8 dynamic, 1360 resource uses; bad blob, index and stage rejected")


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
