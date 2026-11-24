"""Build a packed story catalog from the shipped scene scripts and msgdb.

    python tools/engine/story_catalog.py --dump D:\\Games\\W6W-05 \
        --out build/tmp/story.r6story --report build/tmp/story.json

Only shipped local data is read: ESeries_* XMLT dialogue/timing, Environment.Lua
actor/stage globals and drive_story_* runtime strings. No unlock predicate or
CRC/PLC rival mapping is invented; unresolved numeric fields stay raw.
"""

import argparse
import html
import json
import os
import re
import struct

MAGIC = b"R6STO\0\1\0"
VERSION = 1
HEADER_SIZE = 32
EPISODE_SIZE = 64
MESSAGE_SIZE = 16
EVENT_SIZE = 32
KEY_SIZE = 16

SCENE = os.path.join("data_jp", "scene")
MSGDB = os.path.join("data_jp", "msgdb", "msgdb.lua")
NAME_TABLES = "name_tables.json"
ESERIES_RVA = 0x1e39220

PHASES = (("FrontEvent", 1), ("Race", 2), ("RearEvent", 3))
PHASE_BY_DIR = dict(PHASES)
PHASE_NAMES = {1: "FrontEvent", 2: "Race", 3: "RearEvent"}

EP_FRONT = 1
EP_RACE = 2
EP_REAR = 4
EP_BRANCH_B = 8
EP_ENDING = 16
EP_ENV = 32

EVENT_MESSAGE = 1
EVENT_LETTERING = 2
EVENT_CUTIN_HIT = 3
EVENT_CUTIN_RANGE = 4

LIST_RE = re.compile(
    r"<LIST>\s*<LIST_TYPE>([^<]+)</LIST_TYPE>\s*<DATA>(.*?)</DATA>\s*</LIST>",
    re.S)
SEED_RE = re.compile(r"<SEED>(.*?)</SEED>", re.S)
FIELD_RE = re.compile(r"<([A-Z0-9_]+)>(.*?)</\1>", re.S)
MES_RE = re.compile(r"<MES>(.*?)</MES>", re.S)
ENV_RE = re.compile(r'^\s*([A-Z0-9_]+)\s*=\s*"([^"]*)"', re.M)
MSG_RE = re.compile(
    r'MessageID\s*=\s*"([^"]+)"\s*,\s*Message\s*=\s*"((?:\\.|[^"\\])*)"',
    re.S)
STORY_KEY = re.compile(r"^drive_story_")


def read_text(path, encoding="utf-8-sig"):
    return open(path, "r", encoding=encoding, errors="replace").read()


def name_table(recon, rva):
    tables = json.load(open(os.path.join(recon, NAME_TABLES),
                            encoding="utf8"))["strings"]
    for table in tables:
        if int(table.get("rva", 0)) == rva:
            return list(table["names"])
    raise ValueError("name table 0x%x not found" % rva)


def fields(seed):
    result = {}
    for key, value in FIELD_RE.findall(seed):
        result[key] = html.unescape(value.strip())
    return result


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Strings:
    def __init__(self):
        self.data = bytearray()
        self.offsets = {}

    def add(self, text):
        raw = text.encode("utf8", "replace").replace(b"\0", b"")
        if raw in self.offsets:
            offset = self.offsets[raw]
        else:
            offset = len(self.data)
            self.offsets[raw] = offset
            self.data += raw + b"\0"
        return offset, len(raw)


def lua_string(raw):
    out = bytearray()
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\" or index + 1 >= len(raw):
            out += char.encode("utf8", "replace")
            index += 1
            continue
        index += 1
        code = raw[index]
        index += 1
        if code == "n":
            out += b"\n"
        elif code == "r":
            out += b"\r"
        elif code == "t":
            out += b"\t"
        elif code in ("\\", '"'):
            out += code.encode("ascii")
        elif code == "x" and index + 1 < len(raw):
            out.append(int(raw[index:index + 2], 16) & 0xff)
            index += 2
        elif code.isdigit():
            digits = code
            while len(digits) < 3 and index < len(raw) and raw[index].isdigit():
                digits += raw[index]
                index += 1
            out.append(int(digits) & 0xff)
        else:
            out += code.encode("utf8", "replace")
    return out.decode("utf8", "replace")


def parse_messages(path):
    if not os.path.isfile(path):
        return []
    text = read_text(path)
    block = ""
    for list_type, body in LIST_RE.findall(text):
        if list_type == "MESSAGE_LIST":
            block = body
            break
    return [html.unescape(match.group(1)).strip()
            for match in MES_RE.finditer(block)]


def parse_events(path):
    if not os.path.isfile(path):
        return []
    text = read_text(path)
    result = []
    for list_type, body in LIST_RE.findall(text):
        if list_type == "MESSAGE":
            kind = EVENT_MESSAGE
        elif list_type == "LETTERING":
            kind = EVENT_LETTERING
        elif list_type.startswith("CUT_IN_HIT"):
            kind = EVENT_CUTIN_HIT
        elif list_type.startswith("CUT_IN_RANGE"):
            kind = EVENT_CUTIN_RANGE
        else:
            continue
        for seed in SEED_RE.findall(body):
            row = fields(seed)
            if kind == EVENT_MESSAGE:
                label = row.get("FACE_NAME", "")
            elif kind == EVENT_LETTERING:
                label = row.get("FILE_NAME", "")
            elif kind == EVENT_CUTIN_HIT:
                label = row.get("FACE_NAME", "")
            else:
                label = row.get("TEX_NAME_0", "")
            result.append({
                "kind": kind,
                "start_frame": as_int(row.get("START_FRAME")),
                "end_frame": as_int(row.get("END_FRAME")),
                "range": as_int(row.get("RANGE")),
                "mes_id": as_int(row.get("MES_ID")),
                "actor": as_int(row.get("CAR_ID")),
                "pos": as_int(row.get("POS")),
                "label": label,
            })
    return result


def parse_environment(root):
    result = {
        "actors": [0, 0, 0, 0], "stage": 0, "stage_root": 0,
        "stage_day": 0, "cam_id": 0, "present": 0
    }
    for phase, _ in PHASES:
        path = os.path.join(root, phase, "Environment.Lua")
        if not os.path.isfile(path):
            continue
        values = dict(ENV_RE.findall(read_text(path, "cp932")))
        result["present"] = 1
        for index in range(4):
            result["actors"][index] = as_int(values.get("ACTOR_%d" % index))
        result["stage"] = as_int(values.get("STAGE"))
        result["stage_root"] = as_int(values.get("STAGE_ROOT"))
        result["stage_day"] = as_int(values.get("STAGE_DAY"))
        result["cam_id"] = as_int(values.get("CAM_ID"))
        break
    return result


def build(dump, recon):
    enum_names = name_table(recon, ESERIES_RVA)
    enum_index = {name: index for index, name in enumerate(enum_names)}
    root = os.path.join(dump, SCENE)
    episodes = []
    messages = []
    events = []

    for directory in sorted(os.listdir(root)):
        path = os.path.join(root, directory)
        if not os.path.isdir(path) or not directory.startswith("ESeries_"):
            continue
        ending = directory == "ESeries_Ending"
        match = re.fullmatch(r"ESeries_(\d{3})([AB])?", directory)
        if not ending and not match:
            continue
        if ending:
            enum_name = directory
            enum_id = 0
        else:
            enum_name = directory if directory in enum_index else match.group(0)
            enum_id = enum_index.get(enum_name, 0)
        flags = (EP_ENDING if ending else 0) | \
                (EP_BRANCH_B if directory.endswith("B") else 0)
        env = parse_environment(path)
        flags |= EP_ENV if env["present"] else 0
        episode = len(episodes)
        episode_messages = 0
        episode_events = 0
        for phase_name, phase in PHASES:
            phase_dir = os.path.join(path, phase_name)
            if not os.path.isdir(phase_dir):
                continue
            flags |= 1 << (phase - 1)
            texts = parse_messages(os.path.join(phase_dir, "Message.xmlt"))
            for local_id, text in enumerate(texts):
                messages.append((episode, phase, local_id, text))
            episode_messages += len(texts)
            rows = parse_events(os.path.join(phase_dir, "Event.xmlt"))
            for row in rows:
                row["episode"] = episode
                row["phase"] = phase
                events.append(row)
            episode_events += len(rows)
        episodes.append({
            "name": directory,
            "enum_index": enum_id,
            "flags": flags,
            "message_count": episode_messages,
            "event_count": episode_events,
            "actors": env["actors"],
            "stage": env["stage"],
            "stage_root": env["stage_root"],
            "stage_day": env["stage_day"],
            "cam_id": env["cam_id"],
        })

    text = read_text(os.path.join(dump, MSGDB), "utf-8-sig")
    keys = []
    for key, value in MSG_RE.findall(text):
        if not STORY_KEY.match(key):
            continue
        keys.append((key, lua_string(value)))
    keys.sort(key=lambda row: row[0])
    return {"episodes": episodes, "messages": messages,
            "events": events, "keys": keys}


def pack(sections):
    strings = Strings()
    blob = bytearray(MAGIC)
    blob += struct.pack("<IIIIII", VERSION, len(sections["episodes"]),
                        len(sections["messages"]), len(sections["events"]),
                        len(sections["keys"]), 0)
    string_offset = len(blob)

    for episode in sections["episodes"]:
        name = episode["name"].encode("ascii", "replace")[:31]
        blob += struct.pack("<I32sIHH5HBBB7x", episode["enum_index"],
                            name, episode["flags"],
                            min(episode["message_count"], 0xffff),
                            min(episode["event_count"], 0xffff),
                            *episode["actors"], episode["stage"],
                            episode["stage_root"], episode["stage_day"],
                            episode["cam_id"])
    for episode, phase, local_id, text in sections["messages"]:
        offset, length = strings.add(text)
        blob += struct.pack("<IHHHB5B", offset, episode, local_id,
                            length, phase, 0, 0, 0, 0, 0)
    for event in sections["events"]:
        offset, length = strings.add(event["label"])
        blob += struct.pack("<HBBiiIHBBIH6x", event["episode"], event["phase"],
                            event["kind"], event["start_frame"],
                            event["end_frame"], event["range"],
                            event["mes_id"], event["actor"], event["pos"],
                            offset, length)
    for key, value in sections["keys"]:
        key_offset, key_length = strings.add(key)
        value_offset, value_length = strings.add(value)
        blob += struct.pack("<IIHH4x", key_offset, value_offset,
                            key_length, value_length)

    string_bytes = bytes(strings.data)
    blob += string_bytes
    struct.pack_into("<I", blob, 28, len(string_bytes))
    expected = (HEADER_SIZE + EPISODE_SIZE * len(sections["episodes"]) +
                MESSAGE_SIZE * len(sections["messages"]) +
                EVENT_SIZE * len(sections["events"]) +
                KEY_SIZE * len(sections["keys"]) + len(string_bytes))
    if len(blob) != expected:
        raise ValueError("story catalog layout does not match sizes")
    return bytes(blob)


def unpack_blob(blob):
    count = struct.unpack_from("<IIIIII", blob, 8)
    offset = HEADER_SIZE
    episodes = []
    for _ in range(count[0]):
        row = struct.unpack_from("<I32sIHH5HBBB7x", blob, offset)
        episodes.append({"enum_index": row[0],
                         "name": row[1].rstrip(b"\0").decode("ascii"),
                         "flags": row[2], "message_count": row[3],
                         "event_count": row[4], "actors": list(row[5:9]),
                         "stage": row[9], "stage_root": row[10],
                         "stage_day": row[11], "cam_id": row[12]})
        offset += EPISODE_SIZE
    messages = []
    for _ in range(count[1]):
        row = struct.unpack_from("<IHHHB5B", blob, offset)
        messages.append({"text_offset": row[0], "episode": row[1],
                         "local_id": row[2], "text_len": row[3],
                         "phase": row[4]})
        offset += MESSAGE_SIZE
    events = []
    for _ in range(count[2]):
        row = struct.unpack_from("<HBBiiIHBBIH6x", blob, offset)
        events.append({"episode": row[0], "phase": row[1], "kind": row[2],
                       "start_frame": row[3], "end_frame": row[4],
                       "range": row[5], "mes_id": row[6], "actor": row[7],
                       "pos": row[8], "text_offset": row[9],
                       "text_len": row[10]})
        offset += EVENT_SIZE
    keys = []
    for _ in range(count[3]):
        row = struct.unpack_from("<IIHH4x", blob, offset)
        keys.append({"id_offset": row[0], "value_offset": row[1],
                     "id_len": row[2], "value_len": row[3]})
        offset += KEY_SIZE
    strings = blob[offset:offset + count[4]]
    return episodes, messages, events, keys, strings


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--recon", default=os.path.join(root, "docs", "recon"))
    parser.add_argument("--out")
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    sections = build(args.dump, args.recon)
    blob = pack(sections)
    if args.list:
        for episode in sections["episodes"][:5]:
            print("episode %-16s enum=%d flags=0x%x msg=%d evt=%d" %
                  (episode["name"], episode["enum_index"], episode["flags"],
                   episode["message_count"], episode["event_count"]))
        for message in sections["messages"][:3]:
            print("  msg ep=%d phase=%d id=%d %s" %
                  (message[0], message[1], message[2],
                   message[3].replace("\n", " ")[:60]))
        for event in sections["events"][:3]:
            print("  evt kind=%d frame=%d..%d %s" %
                  (event["kind"], event["start_frame"], event["end_frame"],
                   event["label"]))
        for key in sections["keys"][:3]:
            label = key[1].replace("\n", " ")[:60]
            label = label.encode("ascii", "replace").decode("ascii")
            print("  key %s = %s" % (key[0], label))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "wb").write(blob)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump({"bytes": len(blob),
                       "sections": {key: len(value)
                                    for key, value in sections.items()},
                       **sections}, stream, indent=2, ensure_ascii=False)
    print("story: %d episodes, %d messages, %d events, %d keys, %d bytes" %
          (len(sections["episodes"]), len(sections["messages"]),
           len(sections["events"]), len(sections["keys"]), len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
