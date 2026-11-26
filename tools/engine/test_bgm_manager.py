"""Check the shipped SoundManager BGM id dispatch in C."""

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


class State(ctypes.Structure):
    _fields_ = [("current", ctypes.c_int32), ("next", ctypes.c_int32)]


def buffer(current=-1, next_id=-1, size=0x454):
    raw = bytearray(size)
    if size >= 0x454:
        struct.pack_into("<ii", raw, 0x44C, current, next_id)
    elif size >= 0x450:
        struct.pack_into("<i", raw, 0x44C, current)
    return ctypes.create_string_buffer(bytes(raw), size)


def check(dump):
    playback = audio_events.BGM_PLAYBACK
    assert playback["manager_ids"] == {"current": 0x44C, "next": 0x450,
                                        "no_change": -1}
    assert audio_events.BGM_NO_SOUND == 0x8C
    assert audio_events.BGM_RANDOM == 0x8D
    assert audio_events.BGM_STREAM_HANDLE == 0

    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_bgm_manager_read.restype = ctypes.c_int
    lib.r6_bgm_manager_read.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(State)]
    lib.r6_bgm_manager_select.restype = ctypes.c_int
    lib.r6_bgm_manager_select.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_int32,
                                          ctypes.POINTER(ctypes.c_int32)]

    source = buffer(3, 7)
    out = State()
    assert lib.r6_bgm_manager_read(source, len(source),
                                   ctypes.byref(out)) == R6_OK
    assert (out.current, out.next) == (3, 7)

    cases = [
        (-1, -1, -1, 0, -1, -1),
        (-1, -1, 0x8C, 2, -1, -1),
        (5, 7, 0x8D, 5, 5, 7),
        (-1, 7, 5, 1, 5, 7),
        (5, 7, 5, 4, 5, 7),
        (5, -1, 9, 3, 5, 9),
    ]
    for current, next_id, ident, want_action, want_current, want_next in cases:
        source = buffer(current, next_id)
        action = ctypes.c_int32(-1)
        assert lib.r6_bgm_manager_select(source, len(source), ident,
                                         ctypes.byref(action)) == R6_OK
        assert action.value == want_action, (ident, action.value)
        assert lib.r6_bgm_manager_read(source, len(source),
                                       ctypes.byref(out)) == R6_OK
        assert (out.current, out.next) == (want_current, want_next), ident

    short = buffer(0, 0, 0x453)
    action = ctypes.c_int32(-1)
    assert lib.r6_bgm_manager_select(short, 0x453, 5,
                                     ctypes.byref(action)) == R6_ERR_ARG
    assert lib.r6_bgm_manager_read(short, 0x453,
                                   ctypes.byref(out)) == R6_ERR_ARG
    assert lib.r6_bgm_manager_select(source, len(source), 5,
                                     None) == R6_ERR_ARG
    assert lib.r6_bgm_manager_select(None, len(source), 5,
                                     ctypes.byref(action)) == R6_ERR_ARG
    print("bgm manager: current/next at 0x44c/0x450 and all six playBGM id "
          "dispatch paths match; short buffer and null arguments rejected")


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
