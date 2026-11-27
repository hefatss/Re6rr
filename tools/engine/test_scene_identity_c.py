"""Check the C camera-file identity map against shipped Environment.Lua data."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import scene_identity_catalog as catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x40


class Header(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "version", "record_count", "strings_off", "strings_size")]


class Record(ctypes.Structure):
    _fields_ = [("name_off", ctypes.c_uint32),
                ("matches", ctypes.c_uint32),
                ("cam_id", ctypes.c_int32)]


def configure(lib):
    lib.r6_scene_identity_parse.restype = ctypes.c_int
    lib.r6_scene_identity_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.POINTER(Header)]
    lib.r6_scene_identity_record.restype = ctypes.c_int
    lib.r6_scene_identity_record.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                             ctypes.c_uint32,
                                             ctypes.POINTER(Record)]
    lib.r6_scene_identity_name.restype = ctypes.c_int
    lib.r6_scene_identity_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_uint32, ctypes.c_char_p,
                                           ctypes.c_size_t]
    lib.r6_scene_identity_find.restype = ctypes.c_int
    lib.r6_scene_identity_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_char_p,
                                           ctypes.POINTER(ctypes.c_uint32)]


def check(dump, lib):
    configure(lib)
    rows = catalog.collect(dump)
    blob = catalog.build(rows)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_scene_identity_parse(source, len(blob),
                                       ctypes.byref(header)) == R6_OK
    assert (header.version, header.record_count, header.strings_off,
            header.strings_size) == (1, 59, 732, 730)

    record = Record()
    name = ctypes.create_string_buffer(NAME_CAP)
    index = ctypes.c_uint32()
    for position, row in enumerate(rows):
        assert lib.r6_scene_identity_record(source, len(blob), position,
                                            ctypes.byref(record)) == R6_OK
        assert (record.matches, record.cam_id) == (row["matches"],
                                                   row["cam_id"])
        assert lib.r6_scene_identity_name(source, len(blob), position, name,
                                          len(name)) == R6_OK
        assert name.value.decode("utf8") == row["episode"]
        assert lib.r6_scene_identity_find(
            source, len(blob), row["episode"].encode("utf8"),
            ctypes.byref(index)) == R6_OK
        assert index.value == position

    assert sum(row["matches"] for row in rows) == 58
    exception = next(row for row in rows if not row["matches"])
    assert exception["episode"] == "ESeries_055"
    assert exception["cam_id"] == 2

    assert lib.r6_scene_identity_find(
        source, len(blob), b"R6_NO_SUCH_EPISODE",
        ctypes.byref(index)) == R6_ERR_NOT_FOUND
    assert lib.r6_scene_identity_find(
        source, len(blob), b"", ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_scene_identity_find(
        source, len(blob), None, ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_scene_identity_record(source, len(blob), 59,
                                        ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_scene_identity_record(source, len(blob), 0,
                                        None) == R6_ERR_ARG
    assert lib.r6_scene_identity_name(source, len(blob), 0, name,
                                      4) == R6_ERR_BUFFER

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_identity_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_identity_parse(source, len(bad),
                                       ctypes.byref(header)) == R6_ERR_FORMAT
    struct.pack_into("<I", bad, 12, 59)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_identity_parse(source, len(bad) - 1,
                                       ctypes.byref(header)) == R6_ERR_FORMAT

    print("scene camera identity: 59 shipped episodes, 58 byte-identical "
          "camera files, ESeries_055 exception and all first-exact names "
          "match scene_bridge.build(); bad blob, index and capacity rejected")


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
