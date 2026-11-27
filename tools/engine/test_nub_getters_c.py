"""Check the C nuSound2 getter view against all shipped .nub tones."""

import ctypes
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
R6_ERR_BUFFER = -6
R6_ERR_FORMAT = -5


class Header(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("bank_id", ctypes.c_uint32),
                ("tone_count", ctypes.c_uint32),
                ("header_size", ctypes.c_uint32),
                ("data_size", ctypes.c_uint32),
                ("first_record", ctypes.c_uint32)]


class Tone(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        "index", "slot", "group", "record_offset", "length", "data_offset",
        "flags", "format_count", "rate", "channels", "bits", "loop_flag")] + [
        ("volume", ctypes.c_float),
        ("three_d_param_no", ctypes.c_uint32),
        ("format_tag", ctypes.c_uint16),
        ("format_channels", ctypes.c_uint16),
        ("block_align", ctypes.c_uint16),
        ("byte_rate", ctypes.c_uint32)]


class Getters(ctypes.Structure):
    _fields_ = [("user_param", ctypes.c_uint32 * 4),
                ("total_samples", ctypes.c_uint32),
                ("codec", ctypes.c_uint32)]


def check(dump, lib):
    lib.r6_nub_parse.restype = ctypes.c_int
    lib.r6_nub_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(Header), ctypes.POINTER(Tone),
                                 ctypes.c_size_t]
    lib.r6_nub_tone_getters.restype = ctypes.c_int
    lib.r6_nub_tone_getters.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(Tone),
                                        ctypes.POINTER(Getters)]
    lib.r6_nub_setup_bytes.restype = ctypes.c_int
    lib.r6_nub_setup_bytes.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(Tone), ctypes.c_void_p]

    banks = nub_audio.collect(dump)["banks"]
    root = os.path.join(dump, nub_audio.SOUND_DIR)
    total = 0
    sample_min = None
    sample_max = 0
    for name, bank in banks.items():
        path = os.path.join(root, name.replace("/", os.sep))
        with open(path, "rb") as stream:
            raw = stream.read()
        source = ctypes.create_string_buffer(raw, len(raw))
        header = Header()
        assert lib.r6_nub_parse(source, len(raw), ctypes.byref(header), None,
                                0) == R6_ERR_BUFFER
        assert header.tone_count == len(bank["tone_records"])
        tones = (Tone * header.tone_count)()
        assert lib.r6_nub_parse(source, len(raw), ctypes.byref(header), tones,
                                header.tone_count) == R6_OK
        getters = Getters()
        setup = ctypes.create_string_buffer(0x30)
        for index, tone in enumerate(tones):
            offset = tone.record_offset
            expected_codec = struct.unpack_from("<I", raw, offset + 0x0c)[0]
            expected_params = struct.unpack_from("<4I", raw, offset + 0xac)
            expected_samples = tone.length // tone.block_align
            assert lib.r6_nub_setup_bytes(
                source, len(raw), ctypes.byref(tone), setup) == R6_OK
            assert setup.raw == raw[offset + 0x30:offset + 0x60], (name, index)
            assert lib.r6_nub_tone_getters(
                source, len(raw), ctypes.byref(tone),
                ctypes.byref(getters)) == R6_OK
            assert getters.codec == expected_codec == 1
            assert list(getters.user_param) == list(expected_params)
            assert getters.total_samples == expected_samples
            sample_min = expected_samples if sample_min is None else min(
                sample_min, expected_samples)
            sample_max = max(sample_max, expected_samples)
            total += 1

    assert total == 781 and sample_min == 735 and sample_max == 16027194
    bad = bytearray(raw)
    struct.pack_into("<I", bad, tones[0].record_offset + 0x0c, 2)
    source = ctypes.create_string_buffer(bytes(bad), len(bad))
    assert lib.r6_nub_tone_getters(
        source, len(bad), ctypes.byref(tones[0]),
        ctypes.byref(getters)) == R6_ERR_FORMAT
    assert lib.r6_nub_tone_getters(
        source, len(bad), ctypes.byref(tones[0]), None) == R6_ERR_ARG
    moved = Tone()
    moved.record_offset = len(raw)
    assert lib.r6_nub_tone_getters(
        source, len(bad), ctypes.byref(moved),
        ctypes.byref(getters)) == R6_ERR_ARG
    assert lib.r6_nub_setup_bytes(
        source, len(bad), ctypes.byref(tones[0]), None) == R6_ERR_ARG
    assert lib.r6_nub_setup_bytes(
        source, len(bad), ctypes.byref(moved), setup) == R6_ERR_ARG
    assert lib.r6_nub_setup_bytes(
        None, len(bad), ctypes.byref(tones[0]), setup) == R6_ERR_ARG
    print("nuSound2: all 781 codec-1 tones expose four user params, exact "
          "total samples and 0x30 raw registration bytes; bad codec, null "
          "output, bad record and null blob rejected")


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
