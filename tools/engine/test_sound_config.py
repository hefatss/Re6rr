"""Check the C config.bin header reader against the shipped file."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class SoundBin(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32),
                ("header_size", ctypes.c_uint32),
                ("float_offset", ctypes.c_uint32),
                ("counts", ctypes.c_uint32 * 6),
                ("offsets", ctypes.c_uint32 * 6)]


def check(dump):
    path = os.path.join(dump, "data", "sound", "config.bin")
    with open(path, "rb") as stream:
        raw = bytearray(stream.read())
    want = audio_events.config_header(dump)
    assert want["header_size"] == 0x50
    assert len(want["sections"]) == 6

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_sound_bin_parse.restype = ctypes.c_int
    lib.r6_sound_bin_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(SoundBin)]
    source = ctypes.create_string_buffer(bytes(raw), len(raw))
    out = SoundBin()
    assert lib.r6_sound_bin_parse(source, len(raw),
                                  ctypes.byref(out)) == R6_OK
    assert out.size == want["size"] == len(raw)
    assert out.header_size == want["header_size"]
    assert out.float_offset == want["float_offset"]
    assert list(out.counts) == [pair[0] for pair in want["sections"]]
    assert list(out.offsets) == [pair[1] for pair in want["sections"]]

    bad = []
    for offset, value in ((0, 0), (4, 0), (8, len(raw) + 1), (0x0C, 0x40),
                          (0x14, len(raw) + 1), (0x1C, len(raw) + 1),
                          (0x18 + 5 * 8 + 4, len(raw) + 1)):
        blob = bytearray(raw)
        struct.pack_into("<I", blob, offset, value)
        bad.append(bytes(blob))
    for index, blob in enumerate(bad):
        source = ctypes.create_string_buffer(blob, len(blob))
        out.size = 0xFFFFFFFF
        assert lib.r6_sound_bin_parse(source, len(blob),
                                      ctypes.byref(out)) == R6_ERR_FORMAT, index
        assert out.size == 0, index
    short = ctypes.create_string_buffer(bytes(raw[:-1]), len(raw) - 1)
    assert lib.r6_sound_bin_parse(short, len(raw) - 1,
                                  ctypes.byref(out)) == R6_ERR_FORMAT
    assert lib.r6_sound_bin_parse(None, len(raw),
                                  ctypes.byref(out)) == R6_ERR_FORMAT
    assert lib.r6_sound_bin_parse(source, len(raw), None) == R6_ERR_ARG
    print("config.bin: size 0x50 header, float offset and all six count/offset "
          "pairs match; bad magic, version, size, header and section offsets "
          "rejected")


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
