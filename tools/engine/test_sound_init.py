"""Check the Sound::Initialize config parser against the shipped ABI."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "recon"))

import audio_events  # noqa: E402
import test_engine  # noqa: E402
from pe_report import PE  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -3


class SoundInit(ctypes.Structure):
    _fields_ = [("bank_num", ctypes.c_uint32),
                ("reqid_num", ctypes.c_uint32),
                ("stream_num", ctypes.c_uint32),
                ("pointers", ctypes.c_uint64 * 3),
                ("bank_bytes", ctypes.c_uint32),
                ("request_bytes", ctypes.c_uint32),
                ("stream_bytes", ctypes.c_uint32)]


class SoundImplTail(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32),
                ("zero_quad_offset", ctypes.c_uint32),
                ("zero_quad_count", ctypes.c_uint32),
                ("volume_a_offset", ctypes.c_uint32),
                ("volume_b_offset", ctypes.c_uint32),
                ("sentinel_offset", ctypes.c_uint32),
                ("sentinel_value", ctypes.c_uint32),
                ("volume_value", ctypes.c_float)]


def config_bytes(banks=8, requests=0x22, streams=1,
                 pointers=(0x1407D674D, 0x180000000, 0x18001C9E0)):
    # Pointer slots are 8-byte aligned in the 0x28-byte config.
    return struct.pack("<III4xQQQ", banks, requests, streams, *pointers)


def check(dump):
    pe = PE(os.path.join(dump, "wmn6r.exe"))
    facts = audio_events.sound_init_facts(pe)
    assert facts["config_size"] == 0x28
    assert facts["bank_num"] == {"offset": 0, "value": 8, "max": 0x10}
    assert facts["reqid_num"] == {"offset": 4, "value": 0x22, "max": 0x100}
    assert facts["stream_num"] == {"offset": 8, "value": 1, "min": 1,
                                   "max": 0x10}
    assert (facts["config_bin"], facts["config_3d_bin"],
            facts["core_init"]) == (0x10, 0x18, 0x20)
    impl = facts["impl"]
    assert impl["size"] == 0x98
    assert impl["stream_buffer_size"] == 0xAC440 and impl["output_mode"] == 4
    assert impl["zero_quad_offset"] == 0x60
    assert impl["volume_offsets"] == (0x80, 0x88)
    assert impl["sentinel_offset"] == 0x90

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_sound_init_parse.restype = ctypes.c_int
    lib.r6_sound_init_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(SoundInit)]
    raw = config_bytes()
    source = ctypes.create_string_buffer(raw, len(raw))
    out = SoundInit()
    assert lib.r6_sound_init_parse(source, len(raw), ctypes.byref(out)) == R6_OK
    assert (out.bank_num, out.reqid_num, out.stream_num) == (8, 0x22, 1)
    assert list(out.pointers) == [0x1407D674D, 0x180000000, 0x18001C9E0]
    assert out.bank_bytes == 8 * impl["banks"]["stride"]
    assert out.request_bytes == 0x22 * impl["requests"]["stride"]
    assert out.stream_bytes == 1 * impl["streams"]["stride"]

    bad = [config_bytes(banks=0x11), config_bytes(requests=0x101),
           config_bytes(streams=0), config_bytes(streams=0x11),
           raw[:-1]]
    for blob in bad:
        buffer = ctypes.create_string_buffer(blob, len(blob))
        out.bank_num = 0xFFFFFFFF
        assert lib.r6_sound_init_parse(buffer, len(blob),
                                       ctypes.byref(out)) != R6_OK
        assert (out.bank_num, out.reqid_num, out.stream_num) == (0, 0, 0)
    assert lib.r6_sound_init_parse(None, len(raw),
                                   ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_sound_init_parse(source, len(raw), None) == R6_ERR_ARG

    lib.r6_sound_impl_tail.restype = ctypes.c_int
    lib.r6_sound_impl_tail.argtypes = [ctypes.POINTER(SoundImplTail)]
    tail = SoundImplTail()
    assert lib.r6_sound_impl_tail(ctypes.byref(tail)) == R6_OK
    assert tail.size == impl["size"]
    assert tail.zero_quad_offset == impl["zero_quad_offset"]
    assert tail.zero_quad_count == 4
    assert (tail.volume_a_offset, tail.volume_b_offset) == impl[
        "volume_offsets"]
    assert tail.sentinel_offset == impl["sentinel_offset"]
    assert tail.sentinel_value == 0xFFFFFFFF and tail.volume_value == 1.0
    assert lib.r6_sound_impl_tail(None) == R6_ERR_ARG
    print("sound init: shipped 0x28 config counts, three opaque pointer slots, "
          "0x98 Impl vector sizes and tail constants match; bad counts and "
          "short input rejected")


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
