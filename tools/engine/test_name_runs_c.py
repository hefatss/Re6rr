"""Check the C string-pointer-run reader against name_tables.json."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import name_runs_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
BUF = ctypes.c_char_p
RUN_OFF = 28
USER_OFF = RUN_OFF + 521 * 28
NAME_OFF = USER_OFF + 888 * 4


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in
                ("version", "run_count", "name_count", "user_count",
                 "strings_size")]


def configure(lib):
    lib.r6_name_runs_parse.restype = ctypes.c_int
    lib.r6_name_runs_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_name_runs_run.restype = ctypes.c_int
    lib.r6_name_runs_run.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, PU32, PU32,
        PU32, PU32, PU32]
    lib.r6_name_runs_name.restype = ctypes.c_int
    lib.r6_name_runs_name.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, BUF, ctypes.c_size_t]
    lib.r6_name_runs_run_name.restype = ctypes.c_int
    lib.r6_name_runs_run_name.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, U32, BUF, ctypes.c_size_t]
    lib.r6_name_runs_user.restype = ctypes.c_int
    lib.r6_name_runs_user.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32]
    lib.r6_name_runs_find.restype = ctypes.c_int
    lib.r6_name_runs_find.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, PU32, PU32, PU32]


def check(lib):
    configure(lib)
    runs, names, users = name_runs_catalog.collect()
    blob = name_runs_catalog.build(runs, names, users)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_name_runs_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert header.version == 1
    assert header.run_count == 521
    assert header.name_count == 13283
    assert header.user_count == 888
    assert header.strings_size == len(blob) - NAME_OFF - 13283 * 4

    rva = U32()
    size = U32()
    stride = U32()
    count = U32()
    first_name = U32()
    first_user = U32()
    user_count = U32()
    expected_name = 0
    expected_user = 0
    for index, run in enumerate(runs):
        assert lib.r6_name_runs_run(
            source, len(blob), index, ctypes.byref(rva), ctypes.byref(size),
            ctypes.byref(stride), ctypes.byref(count),
            ctypes.byref(first_name), ctypes.byref(first_user),
            ctypes.byref(user_count)) == R6_OK
        assert rva.value == run["rva"]
        assert size.value == run["size"]
        assert stride.value == run["stride"]
        assert count.value == run["count"]
        assert first_name.value == expected_name
        assert first_user.value == expected_user
        assert user_count.value == len(run["users"])
        expected_name += run["count"]
        expected_user += len(run["users"])

    out = ctypes.create_string_buffer(256)
    for index, expected in enumerate(names):
        assert lib.r6_name_runs_name(
            source, len(blob), index, out, len(out)) == R6_OK
        assert out.value.decode("ascii") == expected

    for run_index, run in enumerate(runs):
        for local_index, expected in enumerate(run["names"]):
            assert lib.r6_name_runs_run_name(
                source, len(blob), run_index, local_index, out,
                len(out)) == R6_OK
            assert out.value.decode("ascii") == expected

    for index, expected in enumerate(users):
        assert lib.r6_name_runs_user(
            source, len(blob), index, ctypes.byref(rva)) == R6_OK
        assert rva.value == expected

    needle = b"RAMP_ID"
    global_index = names.index("RAMP_ID")
    run_index = 0
    local_index = 0
    for index, run in enumerate(runs):
        if global_index < first_name_for(runs, index + 1):
            run_index = index
            local_index = global_index - first_name_for(runs, index)
            break
    assert lib.r6_name_runs_find(
        source, len(blob), needle, ctypes.byref(rva), ctypes.byref(stride),
        ctypes.byref(count)) == R6_OK
    assert rva.value == run_index
    assert stride.value == local_index
    assert count.value == global_index
    assert lib.r6_name_runs_find(
        source, len(blob), b"R6_NO_SUCH_NAME", ctypes.byref(rva),
        ctypes.byref(stride), ctypes.byref(count)) == R6_ERR_NOT_FOUND

    assert lib.r6_name_runs_run(
        source, len(blob), 521, ctypes.byref(rva), ctypes.byref(size),
        ctypes.byref(stride), ctypes.byref(count), ctypes.byref(first_name),
        ctypes.byref(first_user), ctypes.byref(user_count)) == R6_ERR_ARG
    assert lib.r6_name_runs_name(
        source, len(blob), 13283, out, len(out)) == R6_ERR_ARG
    assert lib.r6_name_runs_user(
        source, len(blob), 888, ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_name_runs_name(
        source, len(blob), 0, out, 4) == R6_ERR_BUFFER
    assert lib.r6_name_runs_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_name_runs_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(blob)
    struct.pack_into("<I", bad, RUN_OFF + 4, 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_name_runs_run(
        source, len(bad), 0, ctypes.byref(rva), ctypes.byref(size),
        ctypes.byref(stride), ctypes.byref(count), ctypes.byref(first_name),
        ctypes.byref(first_user), ctypes.byref(user_count)) == R6_ERR_FORMAT
    print("name runs: 521 runs, 13283 names and 888 code refs match "
          "name_tables.json; find, bad blob, index, row and capacity rejected")


def first_name_for(runs, index):
    return sum(run["count"] for run in runs[:index])


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check(lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
