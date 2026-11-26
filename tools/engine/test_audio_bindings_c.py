"""Check the shipped Lua sound bindings against the C binding table."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_NOT_FOUND = -7


class Binding(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("address", ctypes.c_uint64),
                ("call", ctypes.c_char_p), ("bank", ctypes.c_int32),
                ("tone", ctypes.c_int32)]


def configure(lib):
    lib.r6_audio_binding_count.restype = ctypes.c_uint32
    lib.r6_audio_binding_count.argtypes = []
    lib.r6_audio_binding.restype = ctypes.c_int
    lib.r6_audio_binding.argtypes = [ctypes.c_uint32, ctypes.POINTER(Binding)]
    lib.r6_audio_binding_find.restype = ctypes.c_int
    lib.r6_audio_binding_find.argtypes = [ctypes.c_char_p,
                                         ctypes.POINTER(Binding)]


def check(dump):
    rows = audio_events.resolved_bindings(dump)
    assert len(rows) == 12
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    assert lib.r6_audio_binding_count() == len(rows)

    binding = Binding()
    for index, want in enumerate(rows):
        assert lib.r6_audio_binding(index, ctypes.byref(binding)) == R6_OK
        assert binding.name.decode("ascii") == want["name"]
        assert binding.call.decode("ascii") == want["call"]
        assert binding.address == want["address"]
        assert binding.bank == (-1 if want["bank"] is None else want["bank"])
        assert binding.tone == (-1 if want["tone"] is None else want["tone"])
        assert lib.r6_audio_binding_find(want["name"].encode("ascii"),
                                         ctypes.byref(binding)) == index
        assert binding.address == want["address"]

    expected_tones = {"PlaySEDecide": ("SELECT", "select.wav"),
                      "PlaySECancel": ("CANCEL", "cancel.wav"),
                      "PlaySEMove": ("CURSOR", "cursor.wav")}
    by_name = dict((row["name"], row) for row in rows)
    for name, (tone, wav) in expected_tones.items():
        assert by_name[name]["tone_name"] == tone
        assert by_name[name]["wav"] == wav
    assert by_name["PlaySE"]["tone"] is None
    assert by_name["PlaySEOfBank"]["bank"] is None
    assert by_name["StopBGM"]["call"] == "stopBgm"

    assert lib.r6_audio_binding(12, ctypes.byref(binding)) == R6_ERR_ARG
    assert lib.r6_audio_binding(0, None) == R6_ERR_ARG
    assert lib.r6_audio_binding_find(b"NO_SUCH_BINDING",
                                     ctypes.byref(binding)) == \
        R6_ERR_NOT_FOUND
    assert lib.r6_audio_binding_find(None, ctypes.byref(binding)) == \
        R6_ERR_ARG
    print("lua audio bindings: all 12 luaL_Reg rows match address, native "
          "call and fixed bank/tone; SELECT/CANCEL/CURSOR resolved, bad index "
          "and missing name checked")


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
