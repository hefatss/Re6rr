"""Check the C EES container parser against all shipped .EES files."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_scene  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Array(ctypes.Structure):
    _fields_ = [("name", ctypes.c_uint32), ("count", ctypes.c_uint32),
                ("stride", ctypes.c_uint32), ("offset", ctypes.c_uint32),
                ("size", ctypes.c_uint32)]


class Header(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_uint32), ("version", ctypes.c_uint32),
                ("file_size", ctypes.c_uint32), ("count", ctypes.c_uint32),
                ("effect_count", ctypes.c_uint32),
                ("header_size", ctypes.c_uint32),
                ("array_count", ctypes.c_uint32),
                ("arrays", Array * 3)]


KIND = {"cam": 0, "car": 1}
NAMES = {"camera_info": 0, "camera_data": 1, "car_disp": 2,
         "car_effect": 3, "car_info": 4}


def configure(lib):
    lib.r6_ees_parse.restype = ctypes.c_int
    lib.r6_ees_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]


def check(dump, lib):
    root = os.path.join(dump, ees_scene.SCENE_DIR)
    count = 0
    kinds = {"cam": 0, "car": 0}
    for directory, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".EES"):
                continue
            with open(os.path.join(directory, name), "rb") as stream:
                raw = stream.read()
            source = ctypes.create_string_buffer(raw, len(raw))
            header = Header()
            assert lib.r6_ees_parse(source, len(raw),
                                    ctypes.byref(header)) == R6_OK, name
            want = ees_scene.parse_ees(raw)
            kinds[want["kind"]] += 1
            assert header.kind == KIND[want["kind"]], name
            assert header.version == want["version"], name
            assert header.file_size == want["file_size"], name
            assert header.count == want["count"], name
            assert header.effect_count == want.get("effect_count", 0), name
            assert header.header_size == want["header_size"], name
            assert header.array_count == len(want["arrays"]), name
            for index, array in enumerate(want["arrays"]):
                got = header.arrays[index]
                assert got.name == NAMES[array["name"]], (name, index)
                assert got.count == array["count"], (name, index)
                assert got.stride == array["stride"], (name, index)
                assert got.offset == array["offset"], (name, index)
                assert got.size == array["size"], (name, index)
            count += 1
    assert count == 1129 and kinds == {"cam": 720, "car": 409}

    header = Header()
    assert lib.r6_ees_parse(None, 0x130, ctypes.byref(header)) == R6_ERR_ARG
    assert lib.r6_ees_parse(bytes(0x12F), 0x12F,
                            ctypes.byref(header)) == R6_ERR_ARG
    assert lib.r6_ees_parse(bytes(0x130), 0x130,
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(0x130)
    struct.pack_into("<I", bad, 0, 0x2712)
    struct.pack_into("<I", bad, 0x110, len(bad))
    bad_source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ees_parse(bad_source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    print("EES container: %d shipped files match ees_scene.parse_ees(); "
          "short, unknown and inconsistent headers rejected" % count)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    check(args.dump, lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
