"""Check the C scene environment reader against shipped Environment.Lua files."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import scene_env_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("dirs", ctypes.c_uint32),
                ("present", ctypes.c_uint32),
                ("actor_slots", ctypes.c_uint32),
                ("present_slots", ctypes.c_uint32),
                ("nonzero", ctypes.c_uint32),
                ("unique_actors", ctypes.c_uint32),
                ("actor_min", ctypes.c_uint32),
                ("actor_max", ctypes.c_uint32),
                ("stages", ctypes.c_uint32),
                ("unique_stages", ctypes.c_uint32),
                ("stage_min", ctypes.c_uint32),
                ("stage_max", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


class Row(ctypes.Structure):
    _fields_ = [("present", ctypes.c_uint32), ("stage", ctypes.c_uint32),
                ("stage_root", ctypes.c_uint32),
                ("stage_day", ctypes.c_uint32), ("cam_id", ctypes.c_uint32),
                ("actors", ctypes.c_uint32 * 4)]


def check(lib, dump):
    lib.r6_scene_env_parse.restype = ctypes.c_int
    lib.r6_scene_env_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(Header)]
    lib.r6_scene_env_name.restype = ctypes.c_int
    lib.r6_scene_env_name.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.c_char_p,
                                      ctypes.c_size_t]
    lib.r6_scene_env_row.restype = ctypes.c_int
    lib.r6_scene_env_row.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_uint32, ctypes.POINTER(Row)]
    lib.r6_scene_env_find.restype = ctypes.c_int
    lib.r6_scene_env_find.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_char_p,
                                      ctypes.POINTER(ctypes.c_uint32)]

    rows = scene_env_catalog.collect(dump)
    summary = scene_env_catalog.summarize(rows)
    blob = scene_env_catalog.build(rows, summary)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_scene_env_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    for field, expected in summary.items():
        assert getattr(header, field) == expected, (field, expected)
    assert header.dirs == 122 and header.present == 59
    assert header.actor_slots == 488 and header.nonzero == 186
    assert header.unique_actors == 36 and header.unique_stages == 26
    assert header.actor_min == 0 and header.actor_max == 220
    assert header.stage_min == 1 and header.stage_max == 149
    assert header.strings_size == len(blob) - (64 + 122 * 40)

    name = ctypes.create_string_buffer(NAME_CAP)
    row = Row()
    index = ctypes.c_uint32()
    for ordinal, expected in enumerate(rows):
        assert lib.r6_scene_env_name(source, len(blob), ordinal, name,
                                     len(name)) == R6_OK
        assert name.value.decode("ascii") == expected["name"]
        assert lib.r6_scene_env_row(source, len(blob), ordinal,
                                    ctypes.byref(row)) == R6_OK
        assert row.present == expected["present"]
        assert row.stage == expected["stage"]
        assert row.stage_root == expected["stage_root"]
        assert row.stage_day == expected["stage_day"]
        assert row.cam_id == expected["cam_id"]
        assert list(row.actors) == expected["actors"]
        assert lib.r6_scene_env_find(source, len(blob),
                                     expected["name"].encode("ascii"),
                                     ctypes.byref(index)) == R6_OK
        assert index.value == ordinal

    assert lib.r6_scene_env_name(source, len(blob), 122, name,
                                 len(name)) == R6_ERR_ARG
    assert lib.r6_scene_env_find(source, len(blob), b"ESeries_999",
                                 ctypes.byref(index)) == R6_ERR_NOT_FOUND
    assert lib.r6_scene_env_find(source, len(blob), None,
                                 ctypes.byref(index)) == R6_ERR_ARG
    assert lib.r6_scene_env_row(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_scene_env_name(source, len(blob), 0, name,
                                 4) == R6_ERR_BUFFER
    assert lib.r6_scene_env_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_env_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 12, 121)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_env_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 64, 0)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_env_name(source, len(bad), 0, name,
                                 len(name)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 68, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_env_row(source, len(bad), 0,
                                ctypes.byref(row)) == R6_ERR_FORMAT
    print("scene env: 122 dirs, 59 present, 488 actor slots, 186 nonzero, "
          "26 stage values and every per-dir row match shipped data; bad "
          "blob, index and capacity rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(lib, args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
