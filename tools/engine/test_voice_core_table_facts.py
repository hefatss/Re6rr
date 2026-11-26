"""Check the core-voice lookup facts against audio_events.py."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402


class Facts(ctypes.Structure):
    _fields_ = [("count", ctypes.c_uint32), ("offset", ctypes.c_uint32),
                ("stride", ctypes.c_uint32), ("mode", ctypes.c_uint32),
                ("lookup_address", ctypes.c_uint64)]


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_voice_core_table_facts.restype = None
    lib.r6_voice_core_table_facts.argtypes = [ctypes.POINTER(Facts)]
    facts = Facts()
    lib.r6_voice_core_table_facts(ctypes.byref(facts))
    want = audio_events.CHAIN_VOICE_STATE["core_voice_table"]
    assert [facts.count, facts.offset, facts.stride] == [
        want["count"], want["offset"], want["stride"]]
    assert facts.mode == audio_events.CHAIN_VOICE_STATE["modes"][-1]
    assert facts.lookup_address == want["lookup"]
    lib.r6_voice_core_table_facts(None)
    print("core-voice table facts: 192 entries at +0x44 stride 0x178, mode 7 "
          "and lookup address match audio_events.py")


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
