"""ctypes checks for the raw .ACT header-prefix reader."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import act_headers_catalog as ah  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)


class Header(ctypes.Structure):
    _fields_ = [("version", U32), ("count", U32),
                ("prefix_size", U32), ("strings_size", U32)]


def configure(lib):
    lib.r6_act_parse.restype = ctypes.c_int
    lib.r6_act_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]
    lib.r6_act_size.restype = ctypes.c_int
    lib.r6_act_size.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32, PU32]
    lib.r6_act_path.restype = ctypes.c_int
    lib.r6_act_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_act_prefix.restype = ctypes.c_int
    lib.r6_act_prefix.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                  ctypes.c_char_p, ctypes.c_size_t]


def check(lib, data, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_act_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.prefix_size,
            header.strings_size) == (
        1, len(data), ah.PREFIX_SIZE,
        len(blob) - 24 - len(data) * ah.RECORD.size)

    size = U32()
    path = ctypes.create_string_buffer(256)
    prefix = ctypes.create_string_buffer(ah.PREFIX_SIZE)
    for index, (want_path, want_size, want_prefix) in enumerate(data):
        assert lib.r6_act_size(source, len(blob), index,
                               ctypes.byref(size)) == R6_OK
        assert size.value == want_size
        assert lib.r6_act_path(source, len(blob), index, path,
                               len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
        assert lib.r6_act_prefix(source, len(blob), index, prefix,
                                 len(prefix)) == R6_OK
        assert prefix.raw == want_prefix
    print("ACT headers: %d RESOURCE:NU paths, sizes and 64-byte prefixes "
          "match the dump" % len(data))

    bad_index = len(data)
    assert lib.r6_act_size(source, len(blob), bad_index,
                           ctypes.byref(size)) == R6_ERR_ARG
    assert lib.r6_act_path(source, len(blob), bad_index, path,
                           len(path)) == R6_ERR_ARG
    assert lib.r6_act_prefix(source, len(blob), bad_index, prefix,
                             len(prefix)) == R6_ERR_ARG
    assert lib.r6_act_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_act_prefix(source, len(blob), 0, prefix, 63) == R6_ERR_BUFFER
    assert lib.r6_act_size(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_act_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_act_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_act_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 8, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_act_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 16, 32)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_act_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_act_path(source, len(bad), 0, path,
                           len(path)) == R6_ERR_FORMAT
    print("ACT header negatives: bad magic/version/prefix, truncation, bad "
          "path, out-of-range index, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    data = ah.collect(args.dump)
    check(lib, data, ah.build(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
