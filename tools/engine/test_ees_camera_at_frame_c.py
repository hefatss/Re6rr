"""Check the C EES frame lookup against the recovered FUN_1401c8f60 oracle."""

import ctypes
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ees_fields  # noqa: E402
import ees_scene  # noqa: E402
import test_engine  # noqa: E402

R6_ERR_ARG = -1


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_ees_camera_at_frame.restype = ctypes.c_int
    lib.r6_ees_camera_at_frame.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_uint32, ctypes.c_uint32,
                                           ctypes.c_int32]

    path = os.path.join(dump, ees_scene.SCENE_DIR, "ESeries_002",
                        "FrontEvent", "CamData.EES")
    with open(path, "rb") as stream:
        raw = stream.read()
    header = ees_scene.parse_ees(raw)
    offset = header["arrays"][1]["offset"]
    rows = ees_fields.camera_rows(raw, header)
    assert len(rows) == 255

    source = ctypes.create_string_buffer(raw, len(raw))
    frames = {-1000, -1, 0, 1, 351, 1000}
    for row in rows:
        frames.add(row["start"])
        if row["end"] is not None and math.isfinite(row["end"]):
            frames.add(row["end"])
    for frame in sorted(frames):
        want = ees_fields.camera_at_frame(rows, frame)
        got = lib.r6_ees_camera_at_frame(source, len(raw), offset, len(rows),
                                         frame)
        assert got == want, (frame, got, want)
    assert any(ees_fields.camera_at_frame(rows, frame) != -1
               for frame in frames)

    assert lib.r6_ees_camera_at_frame(source, len(raw), offset,
                                      len(rows) + 1, 1) == R6_ERR_ARG
    assert lib.r6_ees_camera_at_frame(source, len(raw) - 1, offset,
                                      len(rows), 1) == R6_ERR_ARG
    assert lib.r6_ees_camera_at_frame(None, len(raw), offset,
                                      len(rows), 1) == R6_ERR_ARG
    print("EES camera_at_frame: %d shipped frames match the last-match "
          "oracle; short buffer, overlong count and null input rejected" %
          len(frames))


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
