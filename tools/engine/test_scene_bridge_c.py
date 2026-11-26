"""Check the C Environment.Lua camid bridge against the shipped Python facts."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import scene_bridge as sb  # noqa: E402
import scene_config  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_scene_write_camid.restype = ctypes.c_int
    lib.r6_scene_write_camid.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(ctypes.c_int32)]
    lib.r6_scene_container_offset.restype = ctypes.c_int
    lib.r6_scene_container_offset.argtypes = [ctypes.c_uint32,
                                              ctypes.POINTER(ctypes.c_size_t)]
    lib.r6_scene_runtime_camera.restype = ctypes.c_int
    lib.r6_scene_runtime_camera.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.c_int32]

    assert (sb.CONFIG_OFFSET, sb.CONFIG_CAMID, sb.CONTAINER_BASE,
            sb.CONTAINER_STRIDE, sb.CONTAINER_COUNT, sb.LOADER_CAMID) == \
        (0x740, 0x70, 0x2D78, 0x1B0, 5, 0x48)
    assert scene_config.SLOT_OFFSETS["cam_id"] == 0x24
    assert ees_fields.CAMERA_EMPTY == -1

    for camid in (0, 1, 2, 0xFF, -1):
        scene = bytearray(scene_config.SCENE_SIZE)
        struct.pack_into("<i", scene, 0x24, camid)
        config = bytearray(0x800)
        want = sb.write_camid(scene, config)
        out = ctypes.c_int32(0)
        target = ctypes.create_string_buffer(bytes(config), len(config))
        got = lib.r6_scene_write_camid(bytes(scene), len(scene),
                                       target, len(config), ctypes.byref(out))
        assert got == R6_OK and out.value == want == camid
        assert struct.unpack_from("<i", target.raw, 0x70)[0] == camid

    short_scene = ctypes.create_string_buffer(bytes(0x27), 0x27)
    short_config = ctypes.create_string_buffer(bytes(0x6F), 0x6F)
    out = ctypes.c_int32(0)
    assert lib.r6_scene_write_camid(short_scene, 0x27, short_config, 0x70,
                                    ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_scene_write_camid(None, 0x28, short_config, 0x70,
                                    ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_scene_write_camid(short_scene, 0x28, short_config, 0x70,
                                    None) == R6_ERR_ARG

    offset = ctypes.c_size_t(0)
    for slot in range(sb.CONTAINER_COUNT):
        assert lib.r6_scene_container_offset(slot,
                                             ctypes.byref(offset)) == R6_OK
        assert offset.value == sb.container_offset(slot)
    assert lib.r6_scene_container_offset(5, ctypes.byref(offset)) == \
        R6_ERR_ARG
    assert lib.r6_scene_container_offset(0, None) == R6_ERR_ARG

    rows = [
        {"type": 2, "start": 100, "end": 120, "exact": 0},
        {"type": 2, "start": 110, "end": 130, "exact": 0},
        {"type": -1, "start": -1, "end": None, "exact": 1},
    ]
    packed = b"".join(struct.pack("<iiii", row["type"], row["start"],
                                  -1 if row["end"] is None else row["end"],
                                  row["exact"]) for row in rows)
    source = ctypes.create_string_buffer(packed, len(packed))
    for frame in (99, 100, 115, 120, 121, 130, 200):
        assert lib.r6_scene_runtime_camera(source, len(source), frame) == \
            sb.runtime_camera_at_frame(rows, frame)
    assert lib.r6_scene_runtime_camera(None, len(packed), 100) == -1

    shipped = sb.build(dump)
    assert len(shipped) == 59
    for row in shipped:
        assert lib.r6_scene_container_offset(row["cam_id"],
                                             ctypes.byref(offset)) == R6_OK
        assert offset.value == sb.container_offset(row["cam_id"])
    print("scene bridge: 5 camid values and 59 shipped episodes copy and "
          "resolve container offsets; runtime camera first-match and invalid "
          "buffers match the Python model")


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
