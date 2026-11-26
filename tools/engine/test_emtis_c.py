"""Check the C EMTIS section reader against the shipped table."""

import ctypes
import math
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


class Section(ctypes.Structure):
    _fields_ = [("marker", ctypes.c_int32), ("start", ctypes.c_int32),
                ("length", ctypes.c_int32),
                ("head", ctypes.c_double * 8)]


class Table(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32 * 8),
                ("version_count", ctypes.c_uint32),
                ("header", ctypes.c_double * 64),
                ("header_count", ctypes.c_uint32),
                ("token_count", ctypes.c_uint32),
                ("sections", Section * 16),
                ("section_count", ctypes.c_uint32),
                ("name_count", ctypes.c_uint32),
                ("name_counts", ctypes.c_uint32 * 4)]


def close(got, want):
    return math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-9)


def check(dump, lib):
    lib.r6_emtis_parse.restype = ctypes.c_int
    lib.r6_emtis_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(Table)]
    path = os.path.join(dump, nub_audio.SOUND_DIR, "emtis.tbl")
    with open(path, "rb") as stream:
        raw = stream.read()
    want = audio_tables.parse_emtis(path)
    source = ctypes.create_string_buffer(raw, len(raw))
    table = Table()
    assert lib.r6_emtis_parse(source, len(raw), ctypes.byref(table)) == R6_OK
    assert list(table.version[:table.version_count]) == want["version"]
    assert table.header_count == len(want["header"])
    assert all(close(got, expected)
               for got, expected in zip(table.header, want["header"]))
    assert table.token_count == len(want["tokens"]) == 16365
    assert table.section_count == len(want["sections"]) == 7
    for index, section in enumerate(want["sections"]):
        got = table.sections[index]
        assert got.marker == section["marker"]
        assert got.start == section["start"]
        assert got.length == section["length"]
        assert all(close(a, b) for a, b in zip(got.head, section["head"]))
    assert table.name_count == len(want["names"]) == 416
    assert list(table.name_counts) == [
        want["name_counts"][prefix]
        for prefix in ("Missfire", "Turbin", "Intake", "Engine")]

    bad = b"NOTIS 3 3\n1 2\n3 4\n60026\n"
    source = ctypes.create_string_buffer(bad, len(bad))
    assert lib.r6_emtis_parse(source, len(bad),
                              ctypes.byref(table)) == R6_ERR_FORMAT
    assert lib.r6_emtis_parse(None, len(raw), ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_emtis_parse(source, 0, ctypes.byref(table)) == R6_ERR_ARG
    assert lib.r6_emtis_parse(source, len(bad), None) == R6_ERR_ARG
    print("emtis: 16365 tokens, 7 sections, 44 header values and 416 names "
          "match audio_tables.parse_emtis(); bad magic and null inputs rejected")


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
