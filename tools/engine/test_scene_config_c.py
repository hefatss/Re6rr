"""Check scene packing and native name lookup against scene_config.py."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import scene_config  # noqa: E402
import scene_config_catalog  # noqa: E402
import test_engine  # noqa: E402
import test_scene_config  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7


class Values(ctypes.Structure):
    _fields_ = [("stage", ctypes.c_int32), ("stage_root", ctypes.c_int32),
                ("stage_day", ctypes.c_int32), ("cam_id", ctypes.c_int32),
                ("actors", ctypes.c_int32 * 4)]


class Header(ctypes.Structure):
    _fields_ = [("counts", ctypes.c_uint32 * 3),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def configure(lib):
    lib.r6_scene_pack.restype = ctypes.c_int
    lib.r6_scene_pack.argtypes = [ctypes.POINTER(Values), ctypes.c_void_p,
                                  ctypes.c_size_t]
    lib.r6_scene_names_parse.restype = ctypes.c_int
    lib.r6_scene_names_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(Header)]
    lib.r6_scene_names_get.restype = ctypes.c_int
    lib.r6_scene_names_get.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_int, ctypes.c_int32,
                                      ctypes.c_char_p, ctypes.c_size_t]


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)

    values = test_scene_config.fixtures()
    fixture = {
        "stage": 43, "stage_root": 0, "stage_day": 1, "cam_id": 1,
        "actors": [5, 190, -1, 253],
    }
    packed = Values(fixture["stage"], fixture["stage_root"],
                    fixture["stage_day"], fixture["cam_id"],
                    (ctypes.c_int32 * 4)(*fixture["actors"]))
    scene = ctypes.create_string_buffer(scene_config.SCENE_SIZE)
    assert lib.r6_scene_pack(ctypes.byref(packed), scene,
                             scene_config.SCENE_SIZE) == R6_OK
    assert scene.raw == scene_config.write_scene(fixture)
    assert lib.r6_scene_pack(ctypes.byref(packed), scene,
                             scene_config.SCENE_SIZE - 1) == R6_ERR_ARG
    assert lib.r6_scene_pack(None, scene, scene_config.SCENE_SIZE) == \
        R6_ERR_ARG
    assert lib.r6_scene_pack(ctypes.byref(packed), None,
                             scene_config.SCENE_SIZE) == R6_ERR_ARG

    tables = scene_config_catalog.collect(dump)
    blob = scene_config_catalog.build(tables)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_scene_names_parse(source, len(blob),
                                    ctypes.byref(header)) == R6_OK
    assert list(header.counts) == [254, 149, 5]
    assert header.strings_off == 40 + 4 * (254 + 149 + 5)
    assert header.strings_off + header.strings_size == len(blob)

    name = ctypes.create_string_buffer(0x80)
    for value in range(len(tables["cars"])):
        assert lib.r6_scene_names_get(source, len(blob), 0, value, name,
                                      len(name)) == R6_OK
        assert name.value.decode("ascii") == \
            scene_config.car_id_name(value, tables["cars"])
    for value in (-2, -1, 254, 1000):
        assert lib.r6_scene_names_get(source, len(blob), 0, value, name,
                                      len(name)) == R6_OK
        assert name.value == b"PLC_NON"
    assert lib.r6_scene_names_get(source, len(blob), 0, 5, name,
                                  8) == R6_ERR_BUFFER

    for value in range(1, len(tables["stages"]) + 1):
        assert lib.r6_scene_names_get(source, len(blob), 1, value, name,
                                      len(name)) == R6_OK
        assert name.value.decode("ascii") == \
            scene_config.stage_name(value, tables["stages"])
    for value in (-1, 0, 150):
        assert lib.r6_scene_names_get(source, len(blob), 1, value, name,
                                      len(name)) == R6_ERR_NOT_FOUND
        assert scene_config.stage_name(value, tables["stages"]) is None

    for value in range(len(tables["days"])):
        assert lib.r6_scene_names_get(source, len(blob), 2, value, name,
                                      len(name)) == R6_OK
        assert name.value.decode("ascii") == \
            scene_config.day_name(value, tables["days"])
    for value in (-1, 5):
        assert lib.r6_scene_names_get(source, len(blob), 2, value, name,
                                      len(name)) == R6_ERR_NOT_FOUND
        assert scene_config.day_name(value, tables["days"]) is None

    assert lib.r6_scene_names_get(source, len(blob), 3, 0, name,
                                  len(name)) == R6_ERR_ARG
    assert lib.r6_scene_names_get(source, len(blob), 0, 0, None,
                                  len(name)) == R6_ERR_ARG
    assert lib.r6_scene_names_parse(source, len(blob) - 1,
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    bad_source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_names_parse(bad_source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    struct.pack_into("<I", bad, 8, 2)
    bad_source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_scene_names_parse(bad_source, len(bad),
                                    ctypes.byref(header)) == R6_ERR_FORMAT
    print("scene config: 0x28 packing and all 408 shipped car/stage/day names "
          "match scene_config.py; out-of-range, bad blob and bad kind checked")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    check(args.dump)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
