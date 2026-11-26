"""Check the packed stage-effect catalog against the C reader."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import stage_effect_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7


class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("count", ctypes.c_uint32),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


class Record(ctypes.Structure):
    _fields_ = [("set_off", ctypes.c_uint32),
                ("symbol_off", ctypes.c_uint32),
                ("file_off", ctypes.c_uint32),
                ("tone_name_off", ctypes.c_uint32),
                ("wav_off", ctypes.c_uint32),
                ("bank", ctypes.c_uint16), ("tone", ctypes.c_uint16),
                ("native_tone", ctypes.c_uint16), ("loop", ctypes.c_uint16),
                ("x", ctypes.c_float), ("y", ctypes.c_float),
                ("z", ctypes.c_float)]


def configure(lib):
    lib.r6_stage_effect_parse.restype = ctypes.c_int
    lib.r6_stage_effect_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_stage_effect_get.restype = ctypes.c_int
    lib.r6_stage_effect_get.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_uint32,
                                        ctypes.POINTER(Record)]
    lib.r6_stage_effect_find_symbol.restype = ctypes.c_int
    lib.r6_stage_effect_find_symbol.argtypes = [ctypes.c_void_p,
                                                ctypes.c_size_t,
                                                ctypes.c_char_p,
                                                ctypes.POINTER(Record)]
    lib.r6_stage_effect_string.restype = ctypes.c_char_p
    lib.r6_stage_effect_string.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                           ctypes.c_uint32]


def check(dump):
    rows = stage_effect_catalog.collect(dump)
    blob = stage_effect_catalog.build(rows)
    assert len(rows) == 6
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_stage_effect_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert (header.version, header.count) == (1, 6)
    assert header.strings_off == 32 + 6 * 40
    assert header.strings_off + header.strings_size == len(blob)

    record = Record()
    for index, row in enumerate(rows):
        assert lib.r6_stage_effect_get(source, len(blob), index,
                                       ctypes.byref(record)) == R6_OK
        resolved = row["resolved"]
        expected = (row["set"] or "", row["symbol"], row["file"],
                    resolved["tone_name"], resolved["wav"])
        for offset, want in zip((record.set_off, record.symbol_off,
                                 record.file_off, record.tone_name_off,
                                 record.wav_off), expected):
            assert lib.r6_stage_effect_string(source, len(blob), offset) == \
                want.encode("utf8")
        assert (record.bank, record.tone) == (resolved["bank"],
                                               resolved["tone"])
        assert record.native_tone == row["native_tone"]
        assert record.loop == row["loop"]
        assert (record.x, record.y, record.z) == tuple(row["position"])
        first = next(i for i, other in enumerate(rows)
                     if other["symbol"] == row["symbol"])
        assert lib.r6_stage_effect_find_symbol(source, len(blob),
                                               row["symbol"].encode("utf8"),
                                               ctypes.byref(record)) == first
        assert record.tone == resolved["tone"]

    assert lib.r6_stage_effect_find_symbol(source, len(blob), b"NO_SUCH_TONE",
                                           ctypes.byref(record)) == \
        R6_ERR_NOT_FOUND
    assert lib.r6_stage_effect_get(source, len(blob), 6,
                                   ctypes.byref(record)) == R6_ERR_ARG
    assert lib.r6_stage_effect_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_stage_effect_parse(b"\0" * len(blob), len(blob),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    assert lib.r6_stage_effect_parse(None, len(blob),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("stage effect: 6 shipped symbolic sounds match the C catalog; "
          "symbol lookup, bad magic, short blob and bad index checked")


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
