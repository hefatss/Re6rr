"""Check the copied bank/voice layout facts against audio_events.py."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402


class Facts(ctypes.Structure):
    _fields_ = [("bank_slots", ctypes.c_uint32),
                ("slot_stride", ctypes.c_uint32),
                ("slot_bank_ptr", ctypes.c_uint32),
                ("slot_data_ptr", ctypes.c_uint32),
                ("slot_voice_ids", ctypes.c_uint32),
                ("record_base", ctypes.c_uint32),
                ("record_stride", ctypes.c_uint32),
                ("record_voice_ids", ctypes.c_uint32),
                ("stream_reserve", ctypes.c_uint32),
                ("stream_limit", ctypes.c_uint32),
                ("version", ctypes.c_uint8 * 3),
                ("voice_slots", ctypes.c_uint32),
                ("voice_record_stride", ctypes.c_uint32),
                ("voice_meta_base", ctypes.c_uint32),
                ("voice_meta_stride", ctypes.c_uint32)]


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_audio_layout_facts.restype = None
    lib.r6_audio_layout_facts.argtypes = [ctypes.POINTER(Facts)]
    facts = Facts()
    lib.r6_audio_layout_facts(ctypes.byref(facts))

    bank = audio_events.BANK_REGISTER
    assert [facts.bank_slots, facts.slot_stride, facts.slot_bank_ptr,
            facts.slot_data_ptr, facts.slot_voice_ids] == [
        bank["slots"], bank["slot_stride"], bank["slot_bank_ptr"],
        bank["slot_data_ptr"], bank["slot_voice_ids"]]
    assert [facts.record_base, facts.record_stride,
            facts.record_voice_ids] == [
        bank["record_base"], bank["record_stride"],
        bank["record_voice_ids"]]
    assert [facts.stream_reserve, facts.stream_limit] == [
        bank["stream_reserve"], bank["stream_limit"]]
    assert list(facts.version) == list(bank["version"])
    assert [facts.voice_slots, facts.voice_record_stride,
            facts.voice_meta_base, facts.voice_meta_stride] == [
        audio_events.VOICE_SLOT_COUNT, audio_events.VOICE_RECORD_STRIDE,
        audio_events.VOICE_META_BASE, audio_events.VOICE_META_STRIDE]
    lib.r6_audio_layout_facts(None)
    print("audio layout facts: 5 bank slots, 3 cleanup record fields, stream "
          "limit, bank version and 4 voice/meta fields match audio_events.py")


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
