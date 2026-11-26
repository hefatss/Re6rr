"""Check the recovered KeyOn voice request and chain arithmetic in C."""

import ctypes
import math
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
R6_ERR_BUFFER = -6

POW_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                          ctypes.c_double, ctypes.c_double)
EXP2_FN = ctypes.CFUNCTYPE(ctypes.c_double, ctypes.c_void_p,
                           ctypes.c_double)


class Math(ctypes.Structure):
    _fields_ = [("user", ctypes.c_void_p), ("pow_value", POW_FN),
                ("exp2_value", EXP2_FN)]


class Request(ctypes.Structure):
    _fields_ = [("request", ctypes.c_int32), ("bank", ctypes.c_int32),
                ("bank_info", ctypes.c_int32), ("tone", ctypes.c_uint32),
                ("bank_ptr", ctypes.c_uint64), ("tone_ptr", ctypes.c_uint64),
                ("voice_ptr", ctypes.c_uint64),
                ("chain_tone", ctypes.c_int32), ("extended", ctypes.c_uint32),
                ("reserved", ctypes.c_uint32),
                ("ext_a", ctypes.c_ubyte * 0x34),
                ("ext_b", ctypes.c_ubyte * 0x1C),
                ("volume", ctypes.c_float), ("pan", ctypes.c_float),
                ("flags", ctypes.c_uint32), ("extra_a", ctypes.c_float),
                ("extra_b", ctypes.c_float), ("extra_c", ctypes.c_float)]


def configure(lib):
    for name, argtypes in (
            ("r6_voice_request_init", [ctypes.POINTER(Request)]),
            ("r6_voice_request_set_ext", [ctypes.POINTER(Request),
                                          ctypes.c_int, ctypes.c_void_p,
                                          ctypes.c_size_t]),
            ("r6_voice_request_pack", [ctypes.POINTER(Request),
                                       ctypes.c_void_p, ctypes.c_size_t]),
            ("r6_voice_request_unpack", [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(Request)])):
        function = getattr(lib, name)
        function.restype = ctypes.c_int
        function.argtypes = argtypes
    lib.r6_voice_clamp_unit.restype = ctypes.c_float
    lib.r6_voice_clamp_unit.argtypes = [ctypes.c_float]
    lib.r6_voice_cents_to_pitch.restype = ctypes.c_int
    lib.r6_voice_cents_to_pitch.argtypes = [
        ctypes.POINTER(Math), ctypes.c_double, ctypes.POINTER(ctypes.c_double)]


def set_fields(native, case):
    assert lib_init(native) == R6_OK
    for name in ("request", "bank", "bank_info", "tone", "bank_ptr",
                 "tone_ptr", "voice_ptr", "chain_tone", "extended",
                 "reserved", "volume", "pan", "flags", "extra_a", "extra_b",
                 "extra_c"):
        if name in case:
            setattr(native, name, case[name])
    for a, name in ((False, "ext_a"), (True, "ext_b")):
        blob = case.get(name, b"")
        if blob:
            buffer = ctypes.create_string_buffer(blob, len(blob))
            assert lib_set_ext(native, a, buffer, len(blob)) == R6_OK


def check(dump):
    global lib_init, lib_set_ext
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    lib_init = lib.r6_voice_request_init
    lib_set_ext = lib.r6_voice_request_set_ext
    playback = audio_events.dispatch_facts(dump)["playback"]
    assert playback["voice_stride"] == 0xA0 and \
        playback["request_fields"]["volume"][0] == 0x84 and \
        list(playback["float_defaults"]) == [1.0, 0.0, 0, 0.0, 1.0, 1.0]

    cases = (
        {"request": 1, "bank": 2, "tone": 3},
        {"request": 7, "bank": 3, "tone": 14, "bank_info": 9,
         "bank_ptr": 0x100, "tone_ptr": 0x200, "voice_ptr": 0x300,
         "chain_tone": -1, "volume": 0.5, "pan": -0.25, "flags": 2},
        {"request": 11, "bank": 4, "tone": 21, "extended": 1,
         "ext_a": bytes(range(0x34)), "ext_b": bytes(range(0x1C)),
         "volume": 0.125, "pan": 0.75, "flags": 7, "extra_a": -1.5,
         "extra_b": 0.25, "extra_c": 3.0},
    )
    native = Request()
    packed = ctypes.create_string_buffer(0xA0)
    for case in cases:
        set_fields(native, case)
        want = audio_events.voice_request(
            case.get("request", 1), case.get("bank", 2),
            case.get("tone", 3), bank_info=case.get("bank_info", 0),
            bank_ptr=case.get("bank_ptr", 0),
            tone_ptr=case.get("tone_ptr", 0),
            voice_ptr=case.get("voice_ptr", 0),
            chain_tone=case.get("chain_tone", -1),
            extended=case.get("extended", 0),
            ext_a=case.get("ext_a", b""), ext_b=case.get("ext_b", b""),
            volume=case.get("volume"), pan=case.get("pan"),
            flags=case.get("flags"), extra_a=case.get("extra_a"),
            extra_b=case.get("extra_b"), extra_c=case.get("extra_c"))
        assert len(want) == 0xA0
        assert lib.r6_voice_request_pack(ctypes.byref(native), packed,
                                         len(packed)) == R6_OK
        assert packed.raw == bytes(want)

        source = ctypes.create_string_buffer(bytes(want), len(want))
        got = Request()
        assert lib.r6_voice_request_unpack(source, len(want),
                                           ctypes.byref(got)) == R6_OK
        assert (got.request, got.bank, got.bank_info, got.tone) == \
            struct.unpack_from("<iiiI", want, 0)
        assert (got.bank_ptr, got.tone_ptr, got.voice_ptr) == \
            struct.unpack_from("<QQQ", want, 0x10)
        assert (got.chain_tone, got.extended, got.reserved) == \
            struct.unpack_from("<iiI", want, 0x28)
        assert bytes(got.ext_a) == want[0x34:0x68]
        assert bytes(got.ext_b) == want[0x68:0x84]
        assert (got.volume, got.pan, got.flags, got.extra_a, got.extra_b,
                got.extra_c) == struct.unpack_from("<ffIfff", want, 0x84)

    assert lib.r6_voice_request_init(None) == R6_ERR_ARG
    assert lib.r6_voice_request_set_ext(ctypes.byref(native), False,
                                        b"", 0x35) == R6_ERR_BUFFER
    assert lib.r6_voice_request_set_ext(ctypes.byref(native), True,
                                        b"", 0x1D) == R6_ERR_BUFFER
    assert lib.r6_voice_request_pack(ctypes.byref(native), packed,
                                     0x9F) == R6_ERR_ARG
    assert lib.r6_voice_request_unpack(packed, 0x9F,
                                       ctypes.byref(native)) == R6_ERR_ARG
    assert lib.r6_voice_request_pack(None, packed, 0xA0) == R6_ERR_ARG

    for value in (float("nan"), -0.5, 2.0, 0.25):
        assert lib.r6_voice_clamp_unit(value) == audio_events.clamp_unit(value)

    pow_cb = POW_FN(lambda user, base, exponent: math.pow(base, exponent))
    exp2_cb = EXP2_FN(lambda user, exponent: math.pow(2.0, exponent))
    sink = Math(None, pow_cb, exp2_cb)
    out = ctypes.c_double()
    for cents in (-1200.0, 0.0, 601.25, 1200.0):
        assert lib.r6_voice_cents_to_pitch(ctypes.byref(sink), cents,
                                           ctypes.byref(out)) == R6_OK
        assert abs(out.value - audio_events.cents_to_pitch(cents)) < 1e-12
    assert lib.r6_voice_cents_to_pitch(ctypes.byref(Math()), 0.0,
                                       ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_voice_cents_to_pitch(ctypes.byref(sink), 0.0,
                                       None) == R6_ERR_ARG
    print("voice runtime: %d request records, unit clamp and cents-to-pitch "
          "match the Python ABI; oversize ext, short buffer and missing hook "
          "rejected" % len(cases))


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
