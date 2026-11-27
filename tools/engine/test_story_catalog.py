"""ctypes checks for the packed story catalog parser."""

import argparse
import ctypes
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from test_engine import R6_OK, load_core  # noqa: E402
import story_catalog  # noqa: E402

R6_ERR_ARG = -1
R6_ERR_FORMAT = -5


class Episode(ctypes.Structure):
    _fields_ = [
        ("enum_index", ctypes.c_uint32), ("name", ctypes.c_char * 32),
        ("flags", ctypes.c_uint32), ("message_count", ctypes.c_uint16),
        ("event_count", ctypes.c_uint16), ("actors", ctypes.c_uint16 * 4),
        ("stage", ctypes.c_uint16), ("stage_root", ctypes.c_uint8),
        ("stage_day", ctypes.c_uint8), ("cam_id", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 7),
    ]


class Message(ctypes.Structure):
    _fields_ = [
        ("text_offset", ctypes.c_uint32), ("episode", ctypes.c_uint16),
        ("local_id", ctypes.c_uint16), ("text_len", ctypes.c_uint16),
        ("phase", ctypes.c_uint8), ("pad", ctypes.c_uint8 * 5),
    ]


class Event(ctypes.Structure):
    _fields_ = [
        ("episode", ctypes.c_uint16), ("phase", ctypes.c_uint8),
        ("kind", ctypes.c_uint8), ("start_frame", ctypes.c_int32),
        ("end_frame", ctypes.c_int32), ("range", ctypes.c_uint32),
        ("mes_id", ctypes.c_uint16), ("actor", ctypes.c_uint8),
        ("pos", ctypes.c_uint8), ("text_offset", ctypes.c_uint32),
        ("text_len", ctypes.c_uint16), ("pad", ctypes.c_uint8 * 6),
    ]


class Key(ctypes.Structure):
    _fields_ = [
        ("id_offset", ctypes.c_uint32), ("value_offset", ctypes.c_uint32),
        ("id_len", ctypes.c_uint16), ("value_len", ctypes.c_uint16),
        ("pad", ctypes.c_uint8 * 4),
    ]


class Summary(ctypes.Structure):
    _fields_ = [
        ("message_phase", ctypes.c_uint32 * 3),
        ("event_phase", ctypes.c_uint32 * 3),
        ("event_kind", ctypes.c_uint32 * 4),
        ("branch_b", ctypes.c_uint32),
        ("ending", ctypes.c_uint32),
        ("environment", ctypes.c_uint32),
        ("enum_zero", ctypes.c_uint32),
        ("empty_key_values", ctypes.c_uint32),
    ]


class Catalog(ctypes.Structure):
    _fields_ = [
        ("episodes", ctypes.c_void_p), ("messages", ctypes.c_void_p),
        ("events", ctypes.c_void_p), ("keys", ctypes.c_void_p),
        ("strings", ctypes.c_void_p), ("episode_count", ctypes.c_size_t),
        ("message_count", ctypes.c_size_t), ("event_count", ctypes.c_size_t),
        ("key_count", ctypes.c_size_t), ("string_count", ctypes.c_size_t),
    ]


def text(lib, name, catalog, index, cap=8192):
    out = ctypes.create_string_buffer(cap)
    function = getattr(lib, "r6_story_catalog_" + name)
    function.argtypes = [ctypes.POINTER(Catalog), ctypes.c_size_t,
                         ctypes.c_char_p, ctypes.c_size_t]
    function.restype = ctypes.c_int
    rc = function(ctypes.byref(catalog), index, out, cap)
    return rc, (out.value if rc == R6_OK else b"")


def expected_summary(sections):
    messages = [0, 0, 0]
    phases = [0, 0, 0]
    kinds = [0, 0, 0, 0]
    for _, phase, _, _ in sections["messages"]:
        messages[phase - 1] += 1
    for row in sections["events"]:
        phases[row["phase"] - 1] += 1
        kinds[row["kind"] - 1] += 1
    return (
        tuple(messages), tuple(phases), tuple(kinds),
        sum(1 for row in sections["episodes"]
            if row["flags"] & story_catalog.EP_BRANCH_B),
        sum(1 for row in sections["episodes"]
            if row["flags"] & story_catalog.EP_ENDING),
        sum(1 for row in sections["episodes"]
            if row["flags"] & story_catalog.EP_ENV),
        sum(1 for row in sections["episodes"] if row["enum_index"] == 0),
        sum(1 for _, value in sections["keys"] if not value),
    )


def summary_fields(summary):
    return (
        tuple(summary.message_phase), tuple(summary.event_phase),
        tuple(summary.event_kind), summary.branch_b, summary.ending,
        summary.environment, summary.enum_zero, summary.empty_key_values,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                      "r6_engine.dll"))
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--recon", default=os.path.join(ROOT, "docs", "recon"))
    args = parser.parse_args()

    lib = load_core(args.dll, args.dump)
    failures = []
    sections = story_catalog.build(args.dump, args.recon)
    blob = story_catalog.pack(sections)
    catalog = Catalog()

    lib.r6_story_catalog_parse.argtypes = [
        ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Catalog)]
    lib.r6_story_catalog_parse.restype = ctypes.c_int
    for name, cls, size in (
            ("episode", Episode, story_catalog.EPISODE_SIZE),
            ("message", Message, story_catalog.MESSAGE_SIZE),
            ("event", Event, story_catalog.EVENT_SIZE),
            ("key", Key, story_catalog.KEY_SIZE)):
        if ctypes.sizeof(cls) != size:
            failures.append("%s ctypes size %d, expected %d" %
                            (name, ctypes.sizeof(cls), size))

    rc = lib.r6_story_catalog_parse(blob, len(blob), ctypes.byref(catalog))
    if rc != R6_OK:
        failures.append("parse rc=%d" % rc)
        for failure in failures:
            print("FAIL " + failure)
        return 1
    counts = (catalog.episode_count, catalog.message_count,
              catalog.event_count, catalog.key_count, catalog.string_count)
    expected = tuple(len(sections[key]) for key in
                     ("episodes", "messages", "events", "keys")) + \
               (len(story_catalog.pack(sections)) - story_catalog.HEADER_SIZE -
                story_catalog.EPISODE_SIZE * len(sections["episodes"]) -
                story_catalog.MESSAGE_SIZE * len(sections["messages"]) -
                story_catalog.EVENT_SIZE * len(sections["events"]) -
                story_catalog.KEY_SIZE * len(sections["keys"]),)
    if counts[:4] != expected[:4] or counts[4] == 0:
        failures.append("counts %r, expected %r" % (counts, expected))
    else:
        print("  story catalog: %d episodes, %d messages, %d events, "
              "%d keys, %d string bytes" % counts)

    lib.r6_story_catalog_summary.argtypes = [
        ctypes.POINTER(Catalog), ctypes.POINTER(Summary)]
    lib.r6_story_catalog_summary.restype = ctypes.c_int
    summary = Summary()
    want = expected_summary(sections)
    if lib.r6_story_catalog_summary(ctypes.byref(catalog),
                                    ctypes.byref(summary)) != R6_OK or \
            summary_fields(summary) != want:
        failures.append("summary %r, expected %r" %
                        (summary_fields(summary), want))
    else:
        print("  summary: messages %s, events %s, kinds %s, flags %s" %
              (want[0], want[1], want[2], want[3:]))
    if lib.r6_story_catalog_summary(None, ctypes.byref(summary)) != \
            R6_ERR_ARG or \
            lib.r6_story_catalog_summary(ctypes.byref(catalog), None) != \
            R6_ERR_ARG:
        failures.append("null summary input accepted")

    for name, cls, size in (
            ("episode", Episode, story_catalog.EPISODE_SIZE),
            ("message", Message, story_catalog.MESSAGE_SIZE),
            ("event", Event, story_catalog.EVENT_SIZE),
            ("key", Key, story_catalog.KEY_SIZE)):
        function = getattr(lib, "r6_story_catalog_" + name)
        function.argtypes = [ctypes.POINTER(Catalog), ctypes.c_size_t,
                             ctypes.POINTER(cls)]
        function.restype = ctypes.c_int

    bad = 0
    episodes = sections["episodes"]
    for index in (0, 10, len(episodes) - 1):
        row = Episode()
        if lib.r6_story_catalog_episode(ctypes.byref(catalog), index,
                                        ctypes.byref(row)) != R6_OK:
            bad += 1
            continue
        entry = episodes[index]
        if (row.enum_index != entry["enum_index"] or
                row.name.rstrip(b"\0") != entry["name"].encode("ascii") or
                row.flags != entry["flags"] or
                list(row.actors) != entry["actors"] or
                row.stage != entry["stage"]):
            bad += 1
    messages = sections["messages"]
    for index in (0, 100, len(messages) - 1):
        row = Message()
        if lib.r6_story_catalog_message(ctypes.byref(catalog), index,
                                        ctypes.byref(row)) != R6_OK:
            bad += 1
            continue
        entry = messages[index]
        if row.episode != entry[0] or row.phase != entry[1] or \
                row.local_id != entry[2]:
            bad += 1
    events = sections["events"]
    for index in (0, 100, len(events) - 1):
        row = Event()
        if lib.r6_story_catalog_event(ctypes.byref(catalog), index,
                                      ctypes.byref(row)) != R6_OK:
            bad += 1
            continue
        entry = events[index]
        if (row.episode != entry["episode"] or row.kind != entry["kind"] or
                row.mes_id != entry["mes_id"]):
            bad += 1
    keys = sections["keys"]
    for index in (0, 100, len(keys) - 1):
        row = Key()
        if lib.r6_story_catalog_key(ctypes.byref(catalog), index,
                                    ctypes.byref(row)) != R6_OK:
            bad += 1
            continue
        if row.id_len == 0 or row.value_offset == 0:
            bad += 1
    if bad:
        failures.append("%d/%d sampled records differ" % (bad, 12))
    else:
        print("  sampled episode/message/event/key records round-trip")

    checks = (
        ("message_text", 0, messages[0][3].encode("utf8")),
        ("event_text", 0, events[0]["label"].encode("utf8")),
        ("key_id", 0, keys[0][0].encode("utf8")),
        ("key_value", 0, keys[0][1].encode("utf8")),
    )
    for name, index, want in checks:
        rc, got = text(lib, name, catalog, index)
        if rc != R6_OK or got != want:
            failures.append("%s(0) rc=%d %r, expected %r" %
                            (name, rc, got[:40], want[:40]))
    print("  shared string section returns UTF-8 text")

    lib.r6_story_catalog_find_episode.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_char_p]
    lib.r6_story_catalog_find_episode.restype = ctypes.c_int
    lib.r6_story_catalog_find_key.argtypes = [
        ctypes.POINTER(Catalog), ctypes.c_char_p]
    lib.r6_story_catalog_find_key.restype = ctypes.c_int
    found = lib.r6_story_catalog_find_episode(ctypes.byref(catalog),
                                              b"ESeries_009B")
    want = next(i for i, row in enumerate(episodes)
                if row["name"] == "ESeries_009B")
    if found != want:
        failures.append("find_episode = %d, expected %d" % (found, want))
    found = lib.r6_story_catalog_find_key(ctypes.byref(catalog),
                                          b"drive_story_2_0")
    want = next(i for i, row in enumerate(keys)
                if row[0] == "drive_story_2_0")
    if found != want:
        failures.append("find_key = %d, expected %d" % (found, want))
    if lib.r6_story_catalog_find_episode(ctypes.byref(catalog),
                                         b"ESeries_NOPE") != -1:
        failures.append("unknown episode matched")
    if lib.r6_story_catalog_find_key(ctypes.byref(catalog),
                                     b"drive_story_NOPE") != -1:
        failures.append("unknown story key matched")

    bad = bytearray(blob)
    bad[8:12] = struct.pack("<I", 2)
    if lib.r6_story_catalog_parse(bytes(bad), len(bad),
                                  ctypes.byref(catalog)) != R6_ERR_FORMAT:
        failures.append("bad version accepted")
    bad = bytearray(blob)
    bad[4] = ord("X")
    if lib.r6_story_catalog_parse(bytes(bad), len(bad),
                                  ctypes.byref(catalog)) != R6_ERR_FORMAT:
        failures.append("bad magic accepted")
    if lib.r6_story_catalog_parse(bytes(blob[:-1]), len(blob) - 1,
                                  ctypes.byref(catalog)) != R6_ERR_FORMAT:
        failures.append("truncated blob accepted")
    if lib.r6_story_catalog_parse(bytes(blob), len(blob), None) != R6_ERR_ARG:
        failures.append("null catalog accepted")

    if failures:
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("all story catalog checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
