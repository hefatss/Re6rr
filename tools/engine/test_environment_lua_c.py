"""Check the C Environment.Lua reader against all shipped scene files."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import story_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1


class Values(ctypes.Structure):
    _fields_ = [("stage", ctypes.c_int32), ("stage_root", ctypes.c_int32),
                ("stage_day", ctypes.c_int32), ("cam_id", ctypes.c_int32),
                ("actors", ctypes.c_int32 * 4)]


def expected(raw_bytes):
    text = raw_bytes.decode("cp932")
    values = dict(story_catalog.ENV_RE.findall(text))
    return [story_catalog.as_int(values.get("STAGE")),
            story_catalog.as_int(values.get("STAGE_ROOT")),
            story_catalog.as_int(values.get("STAGE_DAY")),
            story_catalog.as_int(values.get("CAM_ID"))] + \
           [story_catalog.as_int(values.get("ACTOR_%d" % index))
            for index in range(4)]


def check(dump, lib):
    lib.r6_environment_parse.restype = ctypes.c_int
    lib.r6_environment_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(Values)]
    root = os.path.join(dump, story_catalog.SCENE)
    files = []
    for directory, _, names in os.walk(root):
        if "Environment.Lua" in names:
            files.append(os.path.join(directory, "Environment.Lua"))
    assert len(files) == 70, len(files)

    values = Values()
    for path in files:
        with open(path, "rb") as stream:
            raw = stream.read()
        source = ctypes.create_string_buffer(raw, len(raw))
        assert lib.r6_environment_parse(source, len(raw),
                                        ctypes.byref(values)) == R6_OK
        got = [values.stage, values.stage_root, values.stage_day,
               values.cam_id] + list(values.actors)
        assert got == expected(raw), (path, got, expected(raw))

    text = b'-- comment\r\n STAGE = "12"\r\n ACTOR_2 = "-7"\r\n' \
           b' CAM_ID = "bad"\r\n STAGE_DAY = " 5 "\r\n'
    source = ctypes.create_string_buffer(text, len(text))
    assert lib.r6_environment_parse(source, len(text),
                                    ctypes.byref(values)) == R6_OK
    assert [values.stage, values.stage_root, values.stage_day,
            values.cam_id] == [12, 0, 5, 0]
    assert list(values.actors) == [0, 0, -7, 0]
    assert lib.r6_environment_parse(None, len(text),
                                    ctypes.byref(values)) == R6_ERR_ARG
    assert lib.r6_environment_parse(source, 0,
                                    ctypes.byref(values)) == R6_ERR_ARG
    assert lib.r6_environment_parse(source, len(text), None) == R6_ERR_ARG
    print("Environment.Lua: all %d shipped files match story_catalog.ENV_RE; "
          "comments, signs, malformed values and null inputs checked" %
          len(files))


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
