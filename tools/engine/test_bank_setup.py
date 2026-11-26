"""Check the C bank-registration view against the shipped .nub corpus."""

import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import nub_audio  # noqa: E402
import test_engine  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6


class BankTone(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32),
                ("data_offset", ctypes.c_uint32),
                ("formats", ctypes.c_uint32)]


class BankView(ctypes.Structure):
    _fields_ = [("version", ctypes.c_ubyte * 3),
                ("tone_count", ctypes.c_uint32),
                ("data_offset", ctypes.c_uint32),
                ("data_size", ctypes.c_uint32),
                ("record_table", ctypes.c_uint32),
                ("tones", ctypes.POINTER(BankTone))]


def configure(lib):
    lib.r6_bank_setup_init.restype = ctypes.c_int
    lib.r6_bank_setup_init.argtypes = [
        ctypes.POINTER(BankView), ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(BankTone), ctypes.c_size_t]


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    configure(lib)
    root = os.path.join(dump, nub_audio.SOUND_DIR)
    banks = tones = 0
    first = None
    for directory, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".nub"):
                continue
            path = os.path.join(directory, name)
            with open(path, "rb") as stream:
                raw = stream.read()
            want = audio_events.bank_setup_view(raw)
            meta = nub_audio.header(path)
            parsed = nub_audio.tones(path, meta)
            buffer = ctypes.create_string_buffer(raw, len(raw))
            storage = (BankTone * max(1, want["tone_count"]))()
            view = BankView()
            assert lib.r6_bank_setup_init(ctypes.byref(view), buffer, len(raw),
                                          storage, len(storage)) == R6_OK, path
            assert list(view.version) == list(want["version"]), path
            assert (view.tone_count, view.data_offset, view.data_size,
                    view.record_table) == \
                (want["tone_count"], want["data_offset"], want["data_size"],
                 want["record_table"]), path
            for index in range(want["tone_count"]):
                got = storage[index]
                assert (got.length, got.data_offset, got.formats) == \
                    (want["tones"][index]["length"],
                     want["tones"][index]["data_offset"],
                     want["tones"][index]["formats"]), (path, index)
                assert (got.length, got.data_offset, got.formats) == \
                    (parsed[index]["length"], parsed[index]["data_offset"],
                     parsed[index]["format_count"]), (path, index)
            banks += 1
            tones += want["tone_count"]
            if first is None:
                first = (raw, want["tone_count"], want["record_table"])

    assert (banks, tones) == (149, 781)
    raw, count, table = first
    short = ctypes.create_string_buffer(raw[:0x1F])
    bad_version = bytearray(raw)
    bad_version[0] = 9
    bad_table = bytearray(raw)
    struct.pack_into("<I", bad_table, 0x18, len(raw) + 1)
    bad_record = bytearray(raw)
    struct.pack_into("<I", bad_record, table, len(raw) + 1)
    source = ctypes.create_string_buffer(raw, len(raw))
    storage = (BankTone * count)()
    view = BankView()
    for data, size, expected in (
            (short, 0x1F, R6_ERR_BUFFER),
            (ctypes.create_string_buffer(bytes(bad_version)), len(raw),
             R6_ERR_FORMAT),
            (ctypes.create_string_buffer(bytes(bad_table)), len(raw),
             R6_ERR_FORMAT),
            (ctypes.create_string_buffer(bytes(bad_record)), len(raw),
             R6_ERR_FORMAT)):
        assert lib.r6_bank_setup_init(ctypes.byref(view), data, size, storage,
                                      count) == expected
    assert lib.r6_bank_setup_init(ctypes.byref(view), source, len(raw),
                                  storage, count - 1) == R6_ERR_BUFFER
    assert view.tone_count == count
    assert lib.r6_bank_setup_init(ctypes.byref(view), source, len(raw),
                                  storage, count) == R6_OK
    assert lib.r6_bank_setup_init(None, source, len(raw), storage,
                                  count) == R6_ERR_ARG
    assert lib.r6_bank_setup_init(ctypes.byref(view), None, len(raw), storage,
                                  count) == R6_ERR_BUFFER
    print("bank setup: %d banks and %d tones match Python and nub_audio; "
          "bad version, table, record, short input and capacity rejected" %
          (banks, tones))


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
