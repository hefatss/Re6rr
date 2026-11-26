"""Check the C WM4_ENGMAP reader against the shipped table."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_tables  # noqa: E402
import nub_audio  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Pair(ctypes.Structure):
    _fields_ = [("engine_sound", ctypes.c_int32),
                ("group", ctypes.c_int32)]


class Table(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32),
                ("pairs", Pair * 320)]


def check(dump, lib):
    lib.r6_engmap_parse.restype = ctypes.c_int
    lib.r6_engmap_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.POINTER(Table)]
    path = os.path.join(dump, nub_audio.SOUND_DIR, "engmap.tbl")
    with open(path, "rb") as stream:
        raw = stream.read()
    want = audio_tables.parse_engmap(path)
    source = ctypes.create_string_buffer(raw, len(raw))
    table = Table()
    assert lib.r6_engmap_parse(source, len(raw), ctypes.byref(table)) == R6_OK
    assert table.count == want["count"] == 32
    got = [(table.pairs[index].engine_sound, table.pairs[index].group)
           for index in range(len(table.pairs))]
    assert got == [(item["engine_sound"], item["group"])
                   for item in want["pairs"]]

    entry = " ".join(["0", "2"] + ["0"] * 18)
    conflict = "WM4_ENGMAP\n2\n%s %s\n" % (entry, entry.replace("0 2", "0 3", 1))
    source = ctypes.create_string_buffer(conflict.encode("ascii"),
                                         len(conflict))
    assert lib.r6_engmap_parse(source, len(conflict),
                               ctypes.byref(table)) == R6_ERR_FORMAT
    bad = b"BAD\n2\n" + b"0 " * 40
    source = ctypes.create_string_buffer(bad, len(bad))
    assert lib.r6_engmap_parse(source, len(bad),
                               ctypes.byref(table)) == R6_ERR_FORMAT
    assert lib.r6_engmap_parse(None, len(raw), ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_engmap_parse(source, 0, ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_engmap_parse(source, len(bad), None) == R6_ERR_ARG
    print("engmap: 320 shipped engine_sound/group pairs match "
          "audio_tables.parse_engmap(); conflicts, bad magic and null inputs "
          "rejected")


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
