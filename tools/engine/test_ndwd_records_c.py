"""Check bounded C NDWD subrecord, chain and string readers against shipped streams."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "assets"))
sys.path.insert(0, HERE)

import ndwd_records  # noqa: E402
import test_engine  # noqa: E402
import xmd_streams  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7
NAME_CAP = 0x80


class Header(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint32), ("version", ctypes.c_uint16),
                ("group_count", ctypes.c_uint16),
                ("section_size", ctypes.c_uint32 * 4)]


class Group(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32),
                ("name_offset", ctypes.c_uint32),
                ("subrecord_count", ctypes.c_uint16),
                ("subrecord_start", ctypes.c_uint32)]


class Subrecord(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32),
                ("tokens", ctypes.c_uint32 * 4),
                ("extra", ctypes.c_uint16),
                ("chain_offset", ctypes.c_uint32)]


class ChainRecord(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32),
                ("stride", ctypes.c_uint32),
                ("name_offset", ctypes.c_uint32),
                ("flag", ctypes.c_uint8)]


def configure(lib):
    lib.r6_ndwd_parse_header.restype = ctypes.c_int
    lib.r6_ndwd_parse_header.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(Header)]
    lib.r6_ndwd_parse_group.restype = ctypes.c_int
    lib.r6_ndwd_parse_group.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(Header),
                                        ctypes.c_uint32,
                                        ctypes.POINTER(Group)]
    lib.r6_ndwd_parse_subrecord.restype = ctypes.c_int
    lib.r6_ndwd_parse_subrecord.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header),
        ctypes.POINTER(Group), ctypes.c_uint32, ctypes.POINTER(Subrecord)]
    lib.r6_ndwd_parse_chain_record.restype = ctypes.c_int
    lib.r6_ndwd_parse_chain_record.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header),
        ctypes.POINTER(Subrecord), ctypes.c_uint32,
        ctypes.POINTER(ChainRecord)]
    lib.r6_ndwd_string.restype = ctypes.c_int
    lib.r6_ndwd_string.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(Header), ctypes.c_uint32,
                                   ctypes.c_char_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]


def streams(path):
    raw, _ = xmd_streams.load(path, False)
    if raw[:4] == b"NDWD":
        return [raw]
    _, offsets = xmd_streams.parse(raw)
    end = len(raw)
    result = []
    for index, start in enumerate(offsets):
        stop = offsets[index + 1] if index + 1 < len(offsets) else end
        if raw[start:start + 4] == b"NDWD":
            result.append(raw[start:stop])
    return result


def name_at(d, base, offset):
    start = base + offset
    end = d.index(b"\0", start)
    return d[start:end].decode("ascii")


def check_corpus(dump, lib):
    configure(lib)
    files = [os.path.join(directory, name)
             for directory, _, names in os.walk(dump)
             for name in names
             if name.lower().endswith((".mdl", ".nud"))]
    assert len(files) == 981
    stream_total = 0
    sub_total = 0
    record_total = 0
    name_total = 0
    header = Header()
    group = Group()
    sub = Subrecord()
    record = ChainRecord()
    text = ctypes.create_string_buffer(NAME_CAP)
    used = ctypes.c_size_t()
    for path in files:
        for raw in streams(path):
            source = ctypes.create_string_buffer(raw, len(raw))
            want = ndwd_records.stream_info(raw)
            assert lib.r6_ndwd_parse_header(
                source, len(raw), ctypes.byref(header)) == R6_OK, path
            assert header.id == want["id"]
            assert header.version == want["version"]
            assert header.group_count == want["group_count"]
            assert list(header.section_size) == list(want["sizes"])
            base = 0x30 + sum(want["sizes"])
            for gi, want_group in enumerate(want["groups"]):
                assert lib.r6_ndwd_parse_group(
                    source, len(raw), ctypes.byref(header), gi,
                    ctypes.byref(group)) == R6_OK, (path, gi)
                assert group.offset == want_group["offset"]
                assert group.name_offset == want_group["name_off"]
                assert group.subrecord_count == want_group["nsub"]
                assert group.subrecord_start == want_group["sub_start"]
                assert lib.r6_ndwd_string(
                    source, len(raw), ctypes.byref(header),
                    group.name_offset, text, len(text),
                    ctypes.byref(used)) == R6_OK, (path, gi)
                assert text.value.decode("ascii") == name_at(
                    raw, base, want_group["name_off"])
                name_total += 1
                for sj, want_sub in enumerate(want_group["subs"]):
                    assert lib.r6_ndwd_parse_subrecord(
                        source, len(raw), ctypes.byref(header),
                        ctypes.byref(group), sj,
                        ctypes.byref(sub)) == R6_OK, (path, gi, sj)
                    assert sub.offset == want_sub["offset"]
                    assert list(sub.tokens) == list(want_sub["hashes"])
                    assert sub.extra == want_sub["extra"]
                    for ri, want_record in enumerate(want_sub["records"]):
                        assert lib.r6_ndwd_parse_chain_record(
                            source, len(raw), ctypes.byref(header),
                            ctypes.byref(sub), ri,
                            ctypes.byref(record)) == R6_OK, (
                                path, gi, sj, ri)
                        assert (record.offset, record.stride,
                                record.name_offset, record.flag) == \
                            want_record, (path, gi, sj, ri)
                        assert lib.r6_ndwd_string(
                            source, len(raw), ctypes.byref(header),
                            record.name_offset, text, len(text),
                            ctypes.byref(used)) == R6_OK, (path, gi, sj, ri)
                        assert text.value.decode("ascii") == name_at(
                            raw, base, want_record[2])
                        record_total += 1
                    assert lib.r6_ndwd_parse_chain_record(
                        source, len(raw), ctypes.byref(header),
                        ctypes.byref(sub), len(want_sub["records"]),
                        ctypes.byref(record)) == R6_ERR_NOT_FOUND
                    sub_total += 1
            stream_total += 1
    assert (stream_total, sub_total, record_total) == (23570, 44176, 44176)
    print("NDWD readers: %d streams, %d groups/names, %d subrecords and "
          "%d raw chain records match ndwd_records.py; %d strings resolve" %
          (stream_total, name_total, sub_total, record_total, name_total))
    return stream_total, name_total, sub_total, record_total


def synthetic():
    raw = bytearray(0xD8)
    raw[0:4] = b"NDWD"
    struct.pack_into("<I", raw, 4, 1)
    struct.pack_into("<HH", raw, 8, 2, 1)
    struct.pack_into("<4I", raw, 0x10, 0x80, 0x20, 0, 0)
    struct.pack_into("<I", raw, 0x30 + 0x20, 0)
    struct.pack_into("<HI", raw, 0x30 + 0x2A, 1, 0x80)
    struct.pack_into("<4I", raw, 0x90, 0x11, 0x22, 0x33, 0x44)
    struct.pack_into("<4I", raw, 0xA0, 0x10, 0, 0, 0)
    raw[0xAB] = 1
    struct.pack_into("<4I", raw, 0xB0, 0x10, 2, 0, 0)
    raw[0xD0:0xD4] = b"A\0B\0"
    return bytes(raw)


def check_synthetic(lib):
    configure(lib)
    raw = synthetic()
    source = ctypes.create_string_buffer(raw, len(raw))
    header = Header()
    group = Group()
    sub = Subrecord()
    record = ChainRecord()
    text = ctypes.create_string_buffer(NAME_CAP)
    used = ctypes.c_size_t()
    assert lib.r6_ndwd_parse_header(source, len(raw),
                                    ctypes.byref(header)) == R6_OK
    assert lib.r6_ndwd_parse_group(source, len(raw), ctypes.byref(header), 0,
                                   ctypes.byref(group)) == R6_OK
    assert lib.r6_ndwd_parse_subrecord(
        source, len(raw), ctypes.byref(header), ctypes.byref(group), 0,
        ctypes.byref(sub)) == R6_OK
    assert list(sub.tokens) == [0x11, 0x22, 0x33, 0x44]
    assert sub.extra == 0 and sub.chain_offset == 0xA0
    assert lib.r6_ndwd_parse_chain_record(
        source, len(raw), ctypes.byref(header), ctypes.byref(sub), 0,
        ctypes.byref(record)) == R6_OK
    assert (record.offset, record.stride, record.name_offset,
            record.flag) == (0xA0, 0x10, 0, 1)
    assert lib.r6_ndwd_parse_chain_record(
        source, len(raw), ctypes.byref(header), ctypes.byref(sub), 1,
        ctypes.byref(record)) == R6_OK
    assert (record.offset, record.stride, record.name_offset,
            record.flag) == (0xB0, 0x10, 2, 0)
    assert lib.r6_ndwd_parse_chain_record(
        source, len(raw), ctypes.byref(header), ctypes.byref(sub), 2,
        ctypes.byref(record)) == R6_ERR_NOT_FOUND

    assert lib.r6_ndwd_string(source, len(raw), ctypes.byref(header), 0,
                              text, len(text),
                              ctypes.byref(used)) == R6_OK
    assert text.value == b"A"
    assert used.value == 2
    assert lib.r6_ndwd_string(source, len(raw), ctypes.byref(header), 2,
                              text, len(text),
                              ctypes.byref(used)) == R6_OK
    assert text.value == b"B"

    bad = bytearray(raw)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ndwd_parse_header(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(raw)
    struct.pack_into("<H", bad, 8, 3)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ndwd_parse_header(
        source, len(bad), ctypes.byref(header)) == R6_ERR_FORMAT
    source = ctypes.create_string_buffer(raw, len(raw))
    assert lib.r6_ndwd_parse_group(
        source, len(raw), ctypes.byref(header), 1,
        ctypes.byref(group)) == R6_ERR_ARG
    assert lib.r6_ndwd_parse_subrecord(
        source, len(raw), ctypes.byref(header), ctypes.byref(group), 1,
        ctypes.byref(sub)) == R6_ERR_ARG
    assert lib.r6_ndwd_parse_subrecord(
        None, len(raw), ctypes.byref(header), ctypes.byref(group), 0,
        ctypes.byref(sub)) == R6_ERR_ARG
    assert lib.r6_ndwd_parse_subrecord(
        source, len(raw), ctypes.byref(header), ctypes.byref(group), 0,
        None) == R6_ERR_ARG
    assert lib.r6_ndwd_string(source, len(raw), ctypes.byref(header), 0xFFFF,
                              text, len(text),
                              ctypes.byref(used)) == R6_ERR_FORMAT
    small = ctypes.create_string_buffer(1)
    assert lib.r6_ndwd_string(source, len(raw), ctypes.byref(header), 0,
                              small, 1, ctypes.byref(used)) == R6_ERR_BUFFER
    assert used.value == 2
    print("NDWD synthetic: flag-gated two-record chain, exact strings, "
          "bad magic/version, bad indices, bad string offset and short "
          "capacity rejected")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    args = parser.parse_args()
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), args.dump)
    check_corpus(args.dump, lib)
    check_synthetic(lib)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
