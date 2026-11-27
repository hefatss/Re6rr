"""ctypes checks for the raw .NUF header-prefix reader."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nuf_headers_catalog as nh  # noqa: E402
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
    lib.r6_nuf_parse.restype = ctypes.c_int
    lib.r6_nuf_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header)]
    lib.r6_nuf_size.restype = ctypes.c_int
    lib.r6_nuf_size.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32, PU32]
    lib.r6_nuf_path.restype = ctypes.c_int
    lib.r6_nuf_path.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_nuf_prefix.restype = ctypes.c_int
    lib.r6_nuf_prefix.argtypes = [ctypes.c_char_p, ctypes.c_size_t, U32,
                                  ctypes.c_char_p, ctypes.c_size_t]


def check(lib, data, blob):
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_nuf_parse(source, len(blob), ctypes.byref(header)) == R6_OK
    assert (header.version, header.count, header.prefix_size,
            header.strings_size) == (
        1, len(data), nh.PREFIX_SIZE,
        len(blob) - 24 - len(data) * nh.RECORD.size)

    size = U32()
    path = ctypes.create_string_buffer(256)
    prefix = ctypes.create_string_buffer(nh.PREFIX_SIZE)
    magics = {}
    for index, (want_path, want_size, want_prefix) in enumerate(data):
        assert lib.r6_nuf_size(source, len(blob), index,
                               ctypes.byref(size)) == R6_OK
        assert size.value == want_size
        assert lib.r6_nuf_path(source, len(blob), index, path,
                               len(path)) == R6_OK
        assert path.value.decode("ascii") == want_path
        assert lib.r6_nuf_prefix(source, len(blob), index, prefix,
                                 len(prefix)) == R6_OK
        assert prefix.raw == want_prefix
        magics[want_prefix[:4]] = magics.get(want_prefix[:4], 0) + 1
    assert magics == {b"NUF\0": 1, b"NFH\0": 21}
    print("NUF headers: 22 NUF/NFH paths, sizes and 64-byte prefixes match "
          "the dump")

    bad_index = len(data)
    assert lib.r6_nuf_size(source, len(blob), bad_index,
                           ctypes.byref(size)) == R6_ERR_ARG
    assert lib.r6_nuf_path(source, len(blob), bad_index, path,
                           len(path)) == R6_ERR_ARG
    assert lib.r6_nuf_prefix(source, len(blob), bad_index, prefix,
                             len(prefix)) == R6_ERR_ARG
    assert lib.r6_nuf_path(source, len(blob), 0, path, 4) == R6_ERR_BUFFER
    assert lib.r6_nuf_prefix(source, len(blob), 0, prefix, 63) == R6_ERR_BUFFER
    assert lib.r6_nuf_size(source, len(blob), 0, None) == R6_ERR_ARG
    assert lib.r6_nuf_parse(source, len(blob), None) == R6_ERR_ARG
    assert lib.r6_nuf_parse(source, len(blob) - 1,
                            ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nuf_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 8, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nuf_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 16, 32)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nuf_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, 24, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nuf_path(source, len(bad), 0, path,
                           len(path)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[36] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nuf_prefix(source, len(bad), 0, prefix,
                             len(prefix)) == R6_ERR_FORMAT
    print("NUF header negatives: bad magic/version/prefix, truncation, bad "
          "path, out-of-range index, null output and short buffers rejected")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    configure(lib)
    data = nh.collect(args.dump)
    check(lib, data, nh.build(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
