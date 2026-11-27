"""Check the C R6NAM reader against all shipped native pointer-name tables."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import native_names_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7
KINDS = list(native_names_catalog.TABLES)


class Header(ctypes.Structure):
    _fields_ = [("counts", ctypes.c_uint32 * 9),
                ("offsets", ctypes.c_uint32 * 9),
                ("strings_off", ctypes.c_uint32),
                ("strings_size", ctypes.c_uint32)]


def check(dump, lib):
    lib.r6_native_names_parse.restype = ctypes.c_int
    lib.r6_native_names_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(Header)]
    lib.r6_native_names_get.restype = ctypes.c_int
    lib.r6_native_names_get.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_int, ctypes.c_uint32,
                                        ctypes.c_char_p, ctypes.c_size_t]
    lib.r6_native_names_find.restype = ctypes.c_int
    lib.r6_native_names_find.argtypes = [ctypes.c_void_p,
                                         ctypes.c_size_t,
                                         ctypes.c_int,
                                         ctypes.c_char_p,
                                         ctypes.POINTER(ctypes.c_uint32)]

    tables = native_names_catalog.collect(dump)
    blob = native_names_catalog.build(tables)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_native_names_parse(source, len(blob),
                                     ctypes.byref(header)) == R6_OK
    assert list(header.counts) == [len(tables[name]) for name in KINDS]
    assert all(offset == header.strings_off for offset in header.offsets)
    assert header.strings_off + header.strings_size == len(blob)

    name = ctypes.create_string_buffer(0x100)
    total = 0
    for kind, key in enumerate(KINDS):
        for index, want in enumerate(tables[key]):
            assert lib.r6_native_names_get(source, len(blob), kind, index,
                                           name, len(name)) == R6_OK
            assert name.value.decode("utf8") == want, (key, index)
            total += 1
    assert total == 1036

    found_index = ctypes.c_uint32()
    for kind, key in enumerate(KINDS):
        for index, want in enumerate(tables[key]):
            assert lib.r6_native_names_find(
                source, len(blob), kind, want.encode("utf8"),
                ctypes.byref(found_index)) == R6_OK
            assert found_index.value == index
    assert lib.r6_native_names_find(source, len(blob), 0, b"R6_NO_SUCH_NAME",
                                    ctypes.byref(found_index)) == R6_ERR_NOT_FOUND
    assert lib.r6_native_names_find(source, len(blob), 9, b"sequence",
                                    ctypes.byref(found_index)) == R6_ERR_ARG

    assert lib.r6_native_names_get(source, len(blob), 9, 0, name,
                                   len(name)) == R6_ERR_ARG
    assert lib.r6_native_names_get(source, len(blob), 0,
                                   len(tables[KINDS[0]]), name,
                                   len(name)) == R6_ERR_ARG
    assert lib.r6_native_names_get(source, len(blob), 0, 0, None,
                                   len(name)) == R6_ERR_ARG
    assert lib.r6_native_names_parse(source, len(blob) - 1,
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    bad[0] = ord("X")
    bad_source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_native_names_parse(bad_source, len(bad),
                                     ctypes.byref(header)) == R6_ERR_FORMAT
    print("native names: all %d shipped names in 9 tables match the PE "
          "pointer reads; find, bad kind, index, blob and capacity "
          "rejected" % total)


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
