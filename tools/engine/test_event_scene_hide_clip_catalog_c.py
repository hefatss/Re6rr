"""ctypes checks for the packed event-scene hide-clip inventory."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import event_scene_hide_clip_catalog as ehc  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
BUF = ctypes.c_char_p
HEADER_SIZE = 28
SPAN_SIZE = 8
STRING_BASE = HEADER_SIZE + 5 * SPAN_SIZE
FIELDS = ("version", "name_count", "string_size", "table_size",
          "accessor_size")
ACCESSOR = "EventSceneHideClip_GetHideModel"


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in FIELDS]


def configure(lib):
    lib.r6_event_scene_hide_clip_parse.restype = ctypes.c_int
    lib.r6_event_scene_hide_clip_parse.argtypes = [BUF, ctypes.c_size_t,
                                                   ctypes.POINTER(Header)]
    lib.r6_event_scene_hide_clip_name.restype = ctypes.c_int
    lib.r6_event_scene_hide_clip_name.argtypes = [BUF, ctypes.c_size_t, U32,
                                                 BUF, ctypes.c_size_t]
    lib.r6_event_scene_hide_clip_accessor.restype = ctypes.c_int
    lib.r6_event_scene_hide_clip_accessor.argtypes = [BUF, ctypes.c_size_t,
                                                     BUF, ctypes.c_size_t]


def check(lib, collection, blob):
    names, functions = collection
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_event_scene_hide_clip_parse(source, len(blob),
                                              ctypes.byref(header)) == R6_OK
    assert [getattr(header, name) for name in FIELDS] == [
        1, 4, len(blob) - STRING_BASE, 250, 553]

    name = ctypes.create_string_buffer(128)
    for index, expected in enumerate(names):
        assert lib.r6_event_scene_hide_clip_name(source, len(blob), index,
                                                 name, len(name)) == R6_OK
        assert name.value.decode("ascii") == expected
        offset, length = struct.unpack_from(
            "<2I", blob, HEADER_SIZE + index * SPAN_SIZE)
        assert blob[offset:offset + length].decode("ascii") == expected
    accessor = ctypes.create_string_buffer(64)
    assert lib.r6_event_scene_hide_clip_accessor(
        source, len(blob), accessor, len(accessor)) == R6_OK
    assert accessor.value.decode("ascii") == functions[0] == ACCESSOR
    print("Event-scene hide clips: 4 model names and 1 accessor match the "
          "dump")

    assert lib.r6_event_scene_hide_clip_name(source, len(blob), 4,
                                             name, len(name)) == R6_ERR_ARG
    assert lib.r6_event_scene_hide_clip_parse(source, len(blob),
                                              None) == R6_ERR_ARG
    assert lib.r6_event_scene_hide_clip_name(source, len(blob), 0,
                                             None, 128) == R6_ERR_ARG
    assert lib.r6_event_scene_hide_clip_accessor(source, len(blob),
                                                 None, 64) == R6_ERR_ARG
    assert lib.r6_event_scene_hide_clip_name(source, len(blob), 0,
                                             name, 4) == R6_ERR_BUFFER
    assert lib.r6_event_scene_hide_clip_parse(source, len(blob) - 1,
                                              ctypes.byref(header)) == \
        R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_event_scene_hide_clip_parse(source, len(bad),
                                              ctypes.byref(header)) == \
        R6_ERR_FORMAT
    for slot, value in ((8, 2), (12, 3), (16, 0), (20, 249), (24, 552)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, slot, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_event_scene_hide_clip_parse(source, len(bad),
                                                  ctypes.byref(header)) == \
            R6_ERR_FORMAT
    for slot, value in ((0, 0), (1, 0), (1, 200)):
        bad = bytearray(blob)
        struct.pack_into("<I", bad, HEADER_SIZE + slot * 4, value)
        source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_event_scene_hide_clip_parse(source, len(bad),
                                                  ctypes.byref(header)) == \
            R6_ERR_FORMAT
    offset, _ = struct.unpack_from("<2I", blob, HEADER_SIZE)
    bad = bytearray(blob)
    bad[offset] = 0x80
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_event_scene_hide_clip_parse(source, len(bad),
                                              ctypes.byref(header)) == \
        R6_ERR_FORMAT
    offset, _ = struct.unpack_from("<2I", blob, HEADER_SIZE + 4 * SPAN_SIZE)
    bad = bytearray(blob)
    bad[offset] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_event_scene_hide_clip_parse(source, len(bad),
                                              ctypes.byref(header)) == \
        R6_ERR_FORMAT
    print("Event-scene hide-clip negatives: bad magic/header/span/string "
          "fields, out-of-range index, truncation and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    collection = ehc.collect(args.dump)
    check(lib, collection, ehc.build(collection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
