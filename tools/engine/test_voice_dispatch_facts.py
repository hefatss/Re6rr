"""Check extended-KeyOn status facts against the recovered native ABI."""

import ctypes
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import audio_events  # noqa: E402
import test_engine  # noqa: E402


class Facts(ctypes.Structure):
    _fields_ = [("bank_errors", ctypes.c_uint32 * 8),
                ("null_errors", ctypes.c_uint32 * 3),
                ("chain_error", ctypes.c_uint32),
                ("chain_modes", ctypes.c_uint32 * 3),
                ("ext_offsets", ctypes.c_uint32 * 2),
                ("ext_sizes", ctypes.c_uint32 * 2),
                ("game_layout", ctypes.c_uint32 * 5),
                ("addresses", ctypes.c_uint64 * 8)]


class KeyOnUsers(ctypes.Structure):
    _fields_ = [("plain", ctypes.c_uint64 * 6),
                ("point", ctypes.c_uint64 * 6),
                ("line", ctypes.c_uint64 * 2),
                ("extended", ctypes.c_uint32 * 3),
                ("position_floats", ctypes.c_uint32 * 3),
                ("secondary_bytes", ctypes.c_uint32)]


def check(dump):
    lib = test_engine.load_core(
        os.path.join(ROOT, "build", "engine", "r6_engine.dll"), dump)
    lib.r6_voice_dispatch_facts.restype = None
    lib.r6_voice_dispatch_facts.argtypes = [ctypes.POINTER(Facts)]
    facts = Facts()
    lib.r6_voice_dispatch_facts(ctypes.byref(facts))

    bank = audio_events.BANK_SET_ERRORS
    assert list(facts.bank_errors) == [
        bank["bad_index"], bank["bad_format"], bank["byte0_mismatch"],
        bank["no_slot"], bank["null_data"], bank["already_set"],
        bank["voice_fail"], bank["stream_fail"]]
    errors = audio_events.PLAY_3D_SE_LOOP["wrapper_errors"]
    assert list(facts.null_errors) == [
        errors["null_secondary"], errors["null_third"],
        errors["null_position"]]
    ext = audio_events.EXTENDED_KEY_ON
    assert facts.chain_error == ext["chain"]["error"]
    assert list(facts.chain_modes) == list(ext["chain"]["modes"])
    assert list(facts.ext_offsets) == [
        ext["blobs"]["a"]["request_offset"],
        ext["blobs"]["b"]["request_offset"]]
    assert list(facts.ext_sizes) == [
        ext["blobs"]["a"]["size"], ext["blobs"]["b"]["size"]]

    game = audio_events.GAME_PLAY_3D
    assert list(facts.game_layout) == [
        game["position_offset"], game["caller_vectors"], game["vector_bytes"],
        game["copied_block_bytes"], game["voice_slot_stride"]]
    assert list(facts.addresses) == [
        ext["memcpy"], ext["layer"], ext["activator"],
        ext["3d"]["key_set"], ext["3d"]["chgrp"],
        ext["users"]["line"]["get_position"], game["site"], game["thunk"]]
    lib.r6_voice_dispatch_facts(None)

    lib.r6_voice_keyon_users.restype = None
    lib.r6_voice_keyon_users.argtypes = [ctypes.POINTER(KeyOnUsers)]
    users = KeyOnUsers()
    lib.r6_voice_keyon_users(ctypes.byref(users))
    groups = ext["users"]
    assert list(users.plain) == [
        groups["plain"]["handle"], groups["plain"]["id"],
        groups["plain"]["handle_key_on"], groups["plain"]["id_key_on"],
        groups["plain"]["chain"], groups["plain"]["id_chain"]]
    assert list(users.point) == [
        groups["point"]["handle"], groups["point"]["handle_chgrp"],
        groups["point"]["id"], groups["point"]["id_chgrp"],
        groups["point"]["chain"], groups["point"]["id_chain"]]
    assert list(users.line) == [
        groups["line"]["handle"], groups["line"]["id"]]
    assert list(users.extended) == [int(bool(group["extended"]))
                                    for group in (groups["plain"],
                                                  groups["point"],
                                                  groups["line"])]
    assert list(users.position_floats) == [
        0, groups["point"]["position_floats"],
        groups["line"]["position_floats"]]
    assert users.secondary_bytes == groups["point"]["secondary_bytes"]
    lib.r6_voice_keyon_users(None)
    print("voice dispatch facts: 8 bank errors, 3 null errors, chain error "
          "and modes, ext blob layout, game vector sources, 8 addresses and "
          "14 KeyOn wrapper addresses match audio_events.py")


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
