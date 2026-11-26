"""Check the recovered BGM frame and stream-reserve arithmetic in C."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402


def check(dump):
    assert audio_events.BGM_PLAYBACK["frame_rate"] == 60
    assert audio_events.BANK_REGISTER["stream_limit"] == 0x20000000
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_audio_fade_frames_to_ms.restype = ctypes.c_int32
    lib.r6_audio_fade_frames_to_ms.argtypes = [ctypes.c_int32,
                                               ctypes.c_int32]
    lib.r6_audio_stream_reserve.restype = ctypes.c_int64
    lib.r6_audio_stream_reserve.argtypes = [ctypes.c_int64, ctypes.c_int64]

    for now, maximum in ((0, 120), (30, 90), (60, 60), (0, 59), (0, 61),
                         (90, 60)):
        want = audio_events.fade_frames_to_ms(now, maximum)
        assert lib.r6_audio_fade_frames_to_ms(now, maximum) == want, \
            (now, maximum)

    limit = audio_events.BANK_REGISTER["stream_limit"]
    for total, size in ((0, limit), (limit, 1), (0, limit + 1), (100, 200),
                        (0, -1), (limit - 1, 1)):
        want = audio_events.stream_reserve(total, size)
        assert lib.r6_audio_stream_reserve(total, size) == want, \
            (total, size)

    print("audio stream: frame-to-ms and stream reserve match Python at 60 "
          "fps and the 0x20000000 cap")


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
