"""Check the C NSXR/DXBC container reader against all shipped .nsh files."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import nsxr_shader  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Chunk(ctypes.Structure):
    _fields_ = [("tag", ctypes.c_uint32), ("offset", ctypes.c_uint32),
                ("size", ctypes.c_uint32),
                ("data_offset", ctypes.c_uint32)]


class Record(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32), ("count", ctypes.c_uint32),
                ("dxbc_size", ctypes.c_uint32),
                ("reserved", ctypes.c_uint32),
                ("dxbc_offset", ctypes.c_uint32),
                ("dxbc_version", ctypes.c_uint32),
                ("dxbc_actual_size", ctypes.c_uint32),
                ("chunk_count", ctypes.c_uint32),
                ("digest", ctypes.c_uint8 * 16),
                ("chunks", Chunk * 8)]


class Nsh(ctypes.Structure):
    _fields_ = [("file_size", ctypes.c_uint32),
                ("version", ctypes.c_uint32),
                ("subversion", ctypes.c_uint32),
                ("flags", ctypes.c_uint32),
                ("record_count", ctypes.c_uint32),
                ("table", ctypes.c_uint32 * 5),
                ("records", Record * 2)]


def check(dump, lib):
    lib.r6_nsh_parse.restype = ctypes.c_int
    lib.r6_nsh_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(Nsh)]
    root = os.path.join(dump, nsxr_shader.SHADER_DIR)
    names = sorted(name for name in os.listdir(root) if name.endswith(".nsh"))
    assert len(names) == 223
    chunks = 0
    for name in names:
        with open(os.path.join(root, name), "rb") as stream:
            raw = stream.read()
        want = nsxr_shader.parse_nsh(os.path.join(root, name))
        source = ctypes.create_string_buffer(raw, len(raw))
        got = Nsh()
        assert lib.r6_nsh_parse(source, len(raw), ctypes.byref(got)) == R6_OK, \
            name
        assert got.file_size == want["size"], name
        assert got.version == want["version"], name
        assert got.subversion == want["subversion"], name
        assert got.flags == want["flags"], name
        assert got.record_count == want["record_count"], name
        assert tuple(got.table) == tuple(want["table"]), name
        for index, record in enumerate(want["records"]):
            item = got.records[index]
            assert item.offset == record["offset"], (name, index, "offset")
            assert item.count == record["count"], (name, index, "count")
            assert item.dxbc_size == record["dxbc_size"], (name, index)
            assert item.reserved == record["reserved"], (name, index)
            blob = record["dxbc"]
            assert item.dxbc_offset == blob["raw_offset"], (name, index)
            assert item.dxbc_version == blob["version"], (name, index)
            assert item.dxbc_actual_size == blob["size"], (name, index)
            assert item.chunk_count == len(blob["chunks"]), (name, index)
            assert bytes(item.digest) == bytes.fromhex(blob["digest"]), \
                (name, index, "digest")
            for part_index, part in enumerate(blob["chunks"]):
                cpart = item.chunks[part_index]
                tag, = struct.unpack("<I", part["tag"].encode("ascii"))
                assert cpart.tag == tag, (name, index, part_index, "tag")
                assert cpart.offset == part["offset"], (name, index)
                assert cpart.size == part["size"], (name, index)
                assert cpart.data_offset == part["data_offset"], (name, index)
                chunks += 1

    header = Nsh()
    assert lib.r6_nsh_parse(None, 0x80, ctypes.byref(header)) == R6_ERR_ARG
    assert lib.r6_nsh_parse(bytes(0x7F), 0x7F,
                            ctypes.byref(header)) == R6_ERR_ARG
    bad = bytes(0x80)
    source = ctypes.create_string_buffer(bad, len(bad))
    assert lib.r6_nsh_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_ARG
    good = open(os.path.join(root, names[0]), "rb").read()
    bad = bytearray(good)
    struct.pack_into("<I", bad, 4, len(bad) + 1)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nsh_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    bad = bytearray(good)
    struct.pack_into("<I", bad, 0x80, len(bad))
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nsh_parse(source, len(bad),
                            ctypes.byref(header)) == R6_ERR_FORMAT
    print("NSXR: %d files, 2 records each and %d DXBC chunks match "
          "nsxr_shader.parse_nsh(); short, bad magic and bad sizes rejected" %
          (len(names), chunks))


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
