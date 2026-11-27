"""Check C nuSound2 string-table readers against the shipped tables."""

import ctypes
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nub_audio  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7


class StringsHeader(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("bank_id", ctypes.c_uint32),
                ("count", ctypes.c_uint32), ("size", ctypes.c_uint32),
                ("name_size", ctypes.c_uint32), ("path_size", ctypes.c_uint32),
                ("rows_off", ctypes.c_uint32), ("row_size", ctypes.c_uint32)]


class StringsRow(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char * 0x40),
                ("value", ctypes.c_char * 0x40), ("id", ctypes.c_uint32)]


def configure(lib):
    lib.r6_sound_strings_parse.restype = ctypes.c_int
    lib.r6_sound_strings_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_int,
                                           ctypes.POINTER(StringsHeader)]
    lib.r6_sound_strings_row.restype = ctypes.c_int
    lib.r6_sound_strings_row.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_int, ctypes.c_uint32,
                                        ctypes.POINTER(StringsRow)]
    lib.r6_sound_strings_find.restype = ctypes.c_int
    lib.r6_sound_strings_find.argtypes = [ctypes.c_void_p,
                                          ctypes.c_size_t,
                                          ctypes.c_int,
                                          ctypes.c_char_p,
                                          ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_sound_strings_find_value.restype = ctypes.c_int
    lib.r6_sound_strings_find_value.argtypes = [ctypes.c_void_p,
                                                 ctypes.c_size_t,
                                                 ctypes.c_char_p,
                                                 ctypes.POINTER(ctypes.c_uint32)]


def text(field):
    return bytes(field).split(b"\0", 1)[0]


def check_table(lib, path, kind, source_kind):
    with open(path, "rb") as stream:
        raw = stream.read()
    parsed = nub_audio.parse_string_table(path, source_kind)
    assert parsed["size"] == len(raw)
    source = ctypes.create_string_buffer(raw, len(raw))
    header = StringsHeader()
    assert lib.r6_sound_strings_parse(source, len(raw), kind,
                                      ctypes.byref(header)) == R6_OK
    if kind == 0:
        expected = (1, 0, parsed["count"], parsed["size"],
                    struct.unpack_from("<I", raw, 0x0c)[0], 0, 0x20, 0x30)
    else:
        expected = (1, parsed["bank_id"], parsed["count"], parsed["size"],
                    0x40, 0x40, 0x40, 0x80)
    assert tuple(getattr(header, field) for field in
                 ("version", "bank_id", "count", "size", "name_size",
                  "path_size", "rows_off", "row_size")) == expected

    row = StringsRow()
    for index, want in enumerate(parsed["rows"]):
        assert lib.r6_sound_strings_row(source, len(raw), kind, index,
                                        ctypes.byref(row)) == R6_OK
        assert text(row.name) == want["name"].encode("ascii", "replace")
        assert row.id == want["value"] if kind == 0 else row.id == 0
        if kind == 1:
            assert text(row.value) == want["value"].encode("ascii", "replace")
        else:
            assert text(row.value) == b""
    found = ctypes.c_uint32()
    for index, want in enumerate(parsed["rows"]):
        assert lib.r6_sound_strings_find(
            source, len(raw), kind, want["name"].encode("ascii", "replace"),
            ctypes.byref(found)) == R6_OK
        assert found.value == index
    found_value = ctypes.c_uint32()
    if kind == 1:
        firsts = {}
        for index, want in enumerate(parsed["rows"]):
            firsts.setdefault(want["value"], index)
        for value, first in firsts.items():
            assert lib.r6_sound_strings_find_value(
                source, len(raw), value.encode("ascii", "replace"),
                ctypes.byref(found_value)) == R6_OK
            assert found_value.value == first
        assert lib.r6_sound_strings_find_value(
            source, len(raw), b"R6_NO_SUCH_WAV.wav",
            ctypes.byref(found_value)) == R6_ERR_NOT_FOUND
    else:
        assert lib.r6_sound_strings_find_value(
            source, len(raw), b"BGM",
            ctypes.byref(found_value)) == R6_ERR_FORMAT
    assert lib.r6_sound_strings_find(source, len(raw), kind,
                                     b"R6_NO_SUCH_SOUND_STRING",
                                     ctypes.byref(found)) == R6_ERR_NOT_FOUND
    return parsed


def check(dump):
    root = os.path.join(dump, "data", "sound")
    bank_path = os.path.join(root, "nuSound2BankStr.bin")
    tone_paths = sorted(glob.glob(os.path.join(root, "nuSound2ToneStr*.bin")))
    assert len(tone_paths) == 8

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)

    banks = check_table(lib, bank_path, 0, "bank")
    assert [row["name"] for row in banks["rows"]] == [
        "BGM", "MOVIE", "SYSTEM", "RACE", "MISSFIRE", "OTHERCAR", "RIVALCAR",
        "ENGINE"]
    assert banks["rows"][3]["value"] == 4

    tone_count = 0
    for path in tone_paths:
        parsed = check_table(lib, path, 1, "tone")
        tone_count += parsed["count"]
        if os.path.basename(path) == "nuSound2ToneStrSYSTEM.bin":
            assert len(parsed["rows"]) == 120
            assert parsed["rows"][47]["value"] == "select.wav"
    assert tone_count == 640

    with open(bank_path, "rb") as stream:
        raw = stream.read()
    source = ctypes.create_string_buffer(raw, len(raw))
    header = StringsHeader()
    row = StringsRow()
    assert lib.r6_sound_strings_row(source, len(raw), 0, 8,
                                    ctypes.byref(row)) == R6_ERR_ARG
    assert lib.r6_sound_strings_row(source, len(raw), 2, 0,
                                    ctypes.byref(row)) == R6_ERR_FORMAT
    assert lib.r6_sound_strings_parse(source, len(raw), 2,
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_sound_strings_parse(source, len(raw) - 1, 0,
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_sound_strings_parse(None, len(raw), 0,
                                      ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_sound_strings_row(source, len(raw), 0, 0,
                                    None) == R6_ERR_ARG
    for offset, value in ((0, 2), (8, len(raw) + 1)):
        bad = bytearray(raw)
        struct.pack_into("<I", bad, offset, value)
        bad_source = ctypes.create_string_buffer(bytes(bad), len(bad))
        assert lib.r6_sound_strings_parse(bad_source, len(bad), 0,
                                          ctypes.byref(header)) == \
            R6_ERR_FORMAT
    print("sound strings: 1 bank table and 8 tone tables (%d rows) match "
          "nub_audio.parse_string_table(); bank ids, names and 601 WAV "
          "paths resolve through find/findValue; bad version/size/kind, "
          "short and out-of-range inputs checked" % (8 + tone_count))


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
