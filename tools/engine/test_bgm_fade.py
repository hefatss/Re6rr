"""Check the recovered nuSound2 stream fade state and arithmetic in C."""

import ctypes
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
BAD_ARG = 0xFFFFFFFF
NOT_PLAYING = 0x8000000B
ALREADY_FADING = 0x80000000
SIZE = 0x2C4
F = audio_events.BGM_PLAYBACK["fade_out"]["fields"]


class FadeState(ctypes.Structure):
    _fields_ = [("state", ctypes.c_uint32), ("flag", ctypes.c_uint8),
                ("mode", ctypes.c_uint32), ("frames", ctypes.c_uint32),
                ("step", ctypes.c_float), ("volume", ctypes.c_float),
                ("voice", ctypes.c_uint32), ("channel", ctypes.c_uint32),
                ("fader", ctypes.c_float)]


def record(state=3, flag=0, mode=0, frames=0, step=0.0, volume=0.5,
           voice=0x1234, channel=21, fader=0.75):
    raw = bytearray(b"\xcc" * SIZE)
    struct.pack_into("<I", raw, F["state"], state)
    struct.pack_into("<B", raw, F["fader_flag"], flag)
    struct.pack_into("<I", raw, F["mode"], mode)
    struct.pack_into("<I", raw, F["frames"], frames)
    struct.pack_into("<f", raw, F["step"], step)
    struct.pack_into("<f", raw, F["volume"], volume)
    struct.pack_into("<I", raw, F["voice"], voice)
    struct.pack_into("<I", raw, F["channel"], channel)
    struct.pack_into("<f", raw, F["fader"], fader)
    return raw


def check(dump):
    fade = audio_events.BGM_PLAYBACK["fade_out"]
    assert fade["fields"] == F
    assert (fade["playing"], fade["fading"], fade["stopped"]) == (3, 2, 5)
    assert fade["not_playing"] == NOT_PLAYING
    assert fade["already_fading"] == ALREADY_FADING
    assert audio_events.STREAM_FADE_MS_PER_TICK == 5.333

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_bgm_fade_read.restype = ctypes.c_int
    lib.r6_bgm_fade_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.POINTER(FadeState)]
    lib.r6_bgm_fade_begin.restype = ctypes.c_uint32
    lib.r6_bgm_fade_begin.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.c_int32, ctypes.POINTER(ctypes.c_uint32)]

    raw = record()
    source = ctypes.create_string_buffer(bytes(raw), len(raw))
    out = FadeState()
    assert lib.r6_bgm_fade_read(source, len(raw), ctypes.byref(out)) == R6_OK
    assert (out.state, out.flag, out.mode, out.frames) == (3, 0, 0, 0)
    assert (out.step, out.volume, out.voice, out.channel, out.fader) == \
        (0.0, 0.5, 0x1234, 21, 0.75)

    source = ctypes.create_string_buffer(bytes(raw), len(raw))
    stop = ctypes.c_uint32(0xFFFFFFFF)
    assert lib.r6_bgm_fade_begin(source, len(raw), 2000,
                                 ctypes.byref(stop)) == 0
    assert stop.value == 0
    want_frames = audio_events.stream_fade_frames(2000)
    want_step = audio_events.stream_fade_step(0.5, want_frames)
    updated = source.raw
    assert struct.unpack_from("<I", updated, F["mode"])[0] == 2
    assert struct.unpack_from("<I", updated, F["frames"])[0] == want_frames
    assert struct.unpack_from("<f", updated, F["step"])[0] == \
        ctypes.c_float(want_step).value
    for index in range(SIZE):
        if index in range(F["mode"], F["mode"] + 4) or \
           index in range(F["frames"], F["frames"] + 4) or \
           index in range(F["step"], F["step"] + 4):
            continue
        assert updated[index] == raw[index], index

    for blob, ms, status in (
        (record(mode=2), 2000, ALREADY_FADING),
        (record(state=0), 2000, NOT_PLAYING),
        (record(flag=1), 2000, 0),
        (record(), 0, 0),
        (record(state=9), 2000, 0),
    ):
        source = ctypes.create_string_buffer(bytes(blob), len(blob))
        stop = ctypes.c_uint32(0)
        assert lib.r6_bgm_fade_begin(source, len(blob), ms,
                                     ctypes.byref(stop)) == status
        if status:
            assert source.raw == bytes(blob)
        else:
            state = struct.unpack_from("<I", source.raw, F["state"])[0]
            if blob[F["state"]] == 3 and blob[F["fader_flag"]] == 0 and ms > 0:
                assert state == 3
            else:
                assert state == 5
                assert struct.unpack_from("<f", source.raw, F["fader"])[0] == 0.0
                assert stop.value == 0x1234

    short = ctypes.create_string_buffer(bytes(raw[:-1]), len(raw) - 1)
    assert lib.r6_bgm_fade_begin(short, len(raw) - 1, 2000,
                                 ctypes.byref(stop)) == BAD_ARG
    assert lib.r6_bgm_fade_begin(source, len(raw), 2000, None) == BAD_ARG
    assert lib.r6_bgm_fade_read(source, len(raw) - 1,
                                ctypes.byref(out)) == R6_ERR_ARG
    print("bgm fade: 9 stream fields read exact, 2000 ms produces %d frames "
          "and step %.6f, already-fading/not-playing and fallback stop "
          "match; short input rejected" % (want_frames, want_step))


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
