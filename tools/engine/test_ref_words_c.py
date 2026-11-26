"""Check the C reference-word reader against refs.json."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ref_words_catalog  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_NOT_FOUND = -7
U32 = ctypes.c_uint32
PU32 = ctypes.POINTER(U32)
WORD_OFF = 20
XREF_OFF = WORD_OFF + 98805 * 12


class Header(ctypes.Structure):
    _fields_ = [(name, U32) for name in
                ("version", "word_count", "xref_count")]


def configure(lib):
    lib.r6_ref_words_parse.restype = ctypes.c_int
    lib.r6_ref_words_parse.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Header)]
    lib.r6_ref_words_word.restype = ctypes.c_int
    lib.r6_ref_words_word.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32, PU32, PU32]
    lib.r6_ref_words_xref.restype = ctypes.c_int
    lib.r6_ref_words_xref.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32]
    lib.r6_ref_words_word_xref.restype = ctypes.c_int
    lib.r6_ref_words_word_xref.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, U32, PU32]
    lib.r6_ref_words_find.restype = ctypes.c_int
    lib.r6_ref_words_find.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, U32, PU32]


def check(lib):
    configure(lib)
    words = ref_words_catalog.collect()
    blob = ref_words_catalog.build(words)
    source = ctypes.create_string_buffer(blob, len(blob))
    header = Header()
    assert lib.r6_ref_words_parse(source, len(blob),
                                  ctypes.byref(header)) == R6_OK
    assert header.version == 1
    assert header.word_count == 98805
    assert header.xref_count == 174507
    assert len(blob) == XREF_OFF + 174507 * 4

    value = U32()
    first = U32()
    count = U32()
    firsts = []
    expected = 0
    for index, (expected_value, refs) in enumerate(words):
        assert lib.r6_ref_words_word(
            source, len(blob), index, ctypes.byref(value),
            ctypes.byref(first), ctypes.byref(count)) == R6_OK
        assert value.value == expected_value
        assert first.value == expected
        assert count.value == len(refs)
        firsts.append(expected)
        expected += len(refs)
    assert expected == 174507

    rva = U32()
    for index, (_value, refs) in enumerate(words):
        for local, expected_rva in enumerate(refs):
            assert lib.r6_ref_words_xref(
                source, len(blob), firsts[index] + local,
                ctypes.byref(rva)) == R6_OK
            assert rva.value == expected_rva
            assert lib.r6_ref_words_word_xref(
                source, len(blob), index, local,
                ctypes.byref(rva)) == R6_OK
            assert rva.value == expected_rva

    word_index = U32()
    middle = len(words) // 2
    assert lib.r6_ref_words_find(
        source, len(blob), words[middle][0],
        ctypes.byref(word_index)) == R6_OK
    assert word_index.value == middle
    present = {item[0] for item in words}
    missing = 0xffffffff
    while missing in present:
        missing -= 1
    assert lib.r6_ref_words_find(
        source, len(blob), missing,
        ctypes.byref(word_index)) == R6_ERR_NOT_FOUND

    assert lib.r6_ref_words_word(
        source, len(blob), 98805, ctypes.byref(value), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_ARG
    assert lib.r6_ref_words_xref(
        source, len(blob), 174507, ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_ref_words_word_xref(
        source, len(blob), 0, len(words[0][1]),
        ctypes.byref(rva)) == R6_ERR_ARG
    assert lib.r6_ref_words_parse(source, len(blob) - 1,
                                  ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    bad[0] = ord("X")
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ref_words_parse(source, len(bad),
                                  ctypes.byref(header)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, WORD_OFF, words[1][0])
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ref_words_word(
        source, len(bad), 1, ctypes.byref(value), ctypes.byref(first),
        ctypes.byref(count)) == R6_ERR_FORMAT

    bad = bytearray(blob)
    struct.pack_into("<I", bad, XREF_OFF, 0xffffffff)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_ref_words_xref(
        source, len(bad), 0, ctypes.byref(rva)) == R6_ERR_FORMAT
    print("reference words: 98805 words and 174507 xrefs match refs.json; "
          "find, bad blob, index, row and xref rejected")


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
