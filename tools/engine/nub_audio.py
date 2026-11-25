"""Inventory and extract shipped `nuSound2` .nub PCM banks.

    python tools/engine/nub_audio.py --dump D:\\Games\\W6W-05 --report build/tmp/audio.json
    python tools/engine/nub_audio.py --dump D:\\Games\\W6W-05 \
        --extract BGM.nub --out build/tmp/bgm_01.wav --tone 0

Only shipped data is read. The .nub header locates a tone-record table; each
record carries a PCM length, offset relative to the header block, and WAV
format fields. Extraction writes a standard RIFF/WAVE file with the original
PCM bytes, no resampling or decoding.
"""

import argparse
import json
import os
import struct
import wave

VERSION = 0x00010201
HEADER_SIZE = 0x20
TONE_RECORD_SIZE = 0xd0
STRING_NAME_SIZE = 0x40
STRING_PATH_SIZE = 0x40
SOUND_DIR = os.path.join("data", "sound")


def header(path):
    with open(path, "rb") as stream:
        raw = stream.read(HEADER_SIZE)
    if len(raw) != HEADER_SIZE:
        raise ValueError("short .nub header: %s" % path)
    version, unused, bank_id, tone_count, header_bytes, data_bytes, \
        slot_bytes, first_record = struct.unpack("<8I", raw)
    if version != VERSION:
        raise ValueError("bad .nub version 0x%x: %s" % (version, path))
    if unused != 0 or slot_bytes != 0x20:
        raise ValueError("unexpected .nub header fields: %s" % path)
    if header_bytes < HEADER_SIZE or header_bytes > os.path.getsize(path):
        raise ValueError("bad .nub header size: %s" % path)
    if header_bytes + data_bytes > os.path.getsize(path):
        raise ValueError("bad .nub data size: %s" % path)
    if first_record < HEADER_SIZE or first_record > header_bytes:
        raise ValueError("bad .nub record table: %s" % path)
    return {
        "version": version, "bank_id": bank_id, "tone_count": tone_count,
        "header_size": header_bytes, "data_size": data_bytes,
        "first_record": first_record,
    }


def tones(path, meta=None):
    meta = meta or header(path)
    table_bytes = meta["first_record"] - HEADER_SIZE
    with open(path, "rb") as stream:
        stream.seek(HEADER_SIZE)
        raw = stream.read(table_bytes)
        if len(raw) != table_bytes:
            raise ValueError("short .nub record table: %s" % path)
        slots = struct.unpack("<%dI" % (table_bytes // 4),
                              raw[:table_bytes // 4 * 4])
        offsets = [slot for slot in slots if slot]
        if len(offsets) != meta["tone_count"]:
            raise ValueError("tone count %d, %d record offsets: %s" %
                             (meta["tone_count"], len(offsets), path))
        result = []
        for tone_index, offset in enumerate(offsets):
            if offset < meta["first_record"] or \
                    offset + TONE_RECORD_SIZE > meta["header_size"]:
                raise ValueError("tone record outside header: %s[%d]" %
                                 (path, tone_index))
            stream.seek(offset)
            record = stream.read(TONE_RECORD_SIZE)
            if len(record) != TONE_RECORD_SIZE:
                raise ValueError("short tone record: %s[%d]" %
                                 (path, tone_index))
            codec = record[:8].split(b"\0", 1)[0].decode("ascii", "replace")
            tone_slot, group, flags, length, data_offset, format_count = \
                struct.unpack_from("<6I", record, 8)
            loop_flag = struct.unpack_from("<I", record, 0x28)[0]
            volume = struct.unpack_from("<f", record, 0x34)[0]
            three_d_param_no = struct.unpack_from("<I", record, 0x54)[0]
            format_tag, format_channels = struct.unpack_from("<HH", record,
                                                              0xbc)
            rate, byte_rate, block_align, bits = \
                struct.unpack_from("<IIHH", record, 0xc0)
            width = bits // 8
            if codec != "wav" or width == 0 or block_align == 0:
                raise ValueError("unsupported tone format: %s[%d]" %
                                 (path, tone_index))
            if format_tag != 1 or format_channels != block_align // width:
                raise ValueError("bad WAV format block: %s[%d]" %
                                 (path, tone_index))
            if length % block_align or data_offset + length > meta["data_size"]:
                raise ValueError("tone data outside bank: %s[%d]" %
                                 (path, tone_index))
            if byte_rate != rate * block_align:
                raise ValueError("tone byte rate mismatch: %s[%d]" %
                                 (path, tone_index))
            result.append({
                "index": tone_index, "slot": tone_slot, "group": group,
                "record_offset": offset, "codec": codec,
                "length": length, "data_offset": data_offset,
                "flags": flags, "format_count": format_count, "rate": rate,
                "channels": block_align // width, "bits": bits,
                "loop_flag": loop_flag, "loop": bool(loop_flag & 1),
                "volume": volume, "three_d_param_no": three_d_param_no,
                "format_tag": format_tag, "format_channels": format_channels,
                "block_align": block_align, "byte_rate": byte_rate,
            })
        return result


def parse_nub(path):
    meta = header(path)
    meta["tone_records"] = tones(path, meta)
    return meta


def parse_string_table(path, kind):
    with open(path, "rb") as stream:
        raw = stream.read(HEADER_SIZE)
        fields = struct.unpack("<8I", raw)
        version = fields[0]
        if version != 1:
            raise ValueError("bad %s string table: %s" % (kind, path))
        if kind == "bank":
            _, count, size, name_size = fields[:4]
            bank_id = -1
            path_size = 0
            row_size = 0x30
            if count == 0 or size != HEADER_SIZE + count * row_size - \
                    (row_size - name_size):
                raise ValueError("bad bank string table: %s" % path)
        else:
            _, bank_id, count, size, name_size, path_size = fields[:6]
            if name_size != STRING_NAME_SIZE or \
                    path_size != STRING_PATH_SIZE:
                raise ValueError("bad tone string table: %s" % path)
            row_size = name_size + path_size
            if size != HEADER_SIZE + 0x20 + count * row_size:
                raise ValueError("bad tone string table: %s" % path)
            stream.seek(HEADER_SIZE + 0x20)
        rows = stream.read(count * row_size)
    result = []
    for index in range(count):
        row = rows[index * row_size:(index + 1) * row_size]
        if kind == "bank":
            name = row[:name_size].split(b"\0", 1)[0]
            value = struct.unpack_from("<I", row, name_size)[0] \
                if len(row) >= name_size + 4 else 0
        else:
            name = row[:name_size].split(b"\0", 1)[0]
            value = row[name_size:name_size + path_size].split(b"\0", 1)[0]
        result.append({
            "index": index,
            "name": name.decode("ascii", "replace"),
            "value": value if kind == "bank" else
                     value.decode("ascii", "replace"),
        })
    return {"version": version, "bank_id": bank_id, "count": count,
            "size": size, "rows": result}


def collect(dump):
    root = os.path.join(dump, SOUND_DIR)
    banks = {}
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if not name.endswith(".nub") or not os.path.isfile(path):
            continue
        banks[name] = parse_nub(path)
    bgm = os.path.join(root, "BGM")
    if os.path.isdir(bgm):
        for name in sorted(os.listdir(bgm)):
            path = os.path.join(bgm, name)
            if not name.endswith(".nub") or not os.path.isfile(path):
                continue
            banks[os.path.join("BGM", name)] = parse_nub(path)
    strings = {}
    for name in sorted(os.listdir(root)):
        if not name.startswith("nuSound2") or not name.endswith(".bin"):
            continue
        kind = "bank" if name == "nuSound2BankStr.bin" else "tone"
        strings[name] = parse_string_table(os.path.join(root, name), kind)
    return {"banks": banks, "strings": strings}


def extract(dump, relative, tone_index, output):
    path = os.path.join(dump, SOUND_DIR, relative)
    meta = header(path)
    rows = tones(path, meta)
    if tone_index < 0 or tone_index >= len(rows):
        raise ValueError("tone %d outside %s (%d tones)" %
                         (tone_index, relative, len(rows)))
    row = rows[tone_index]
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(path, "rb") as source, wave.open(output, "wb") as target:
        source.seek(meta["header_size"] + row["data_offset"])
        pcm = source.read(row["length"])
        if len(pcm) != row["length"]:
            raise ValueError("short PCM read from %s[%d]" %
                             (relative, tone_index))
        target.setnchannels(row["channels"])
        target.setsampwidth(row["bits"] // 8)
        target.setframerate(row["rate"])
        target.writeframesraw(pcm)
    return row


def report_text(data):
    banks = data["banks"]
    tone_count = sum(len(bank["tone_records"]) for bank in banks.values())
    rows = ["%d .nub banks, %d tones, %d string tables" %
            (len(banks), tone_count, len(data["strings"]))]
    for name, bank in banks.items():
        formats = sorted({(row["rate"], row["channels"], row["bits"])
                          for row in bank["tone_records"]})
        rows.append("  %-28s bank=%-3d tones=%-3d header=0x%-6x data=0x%-8x %s" %
                    (name, bank["bank_id"], len(bank["tone_records"]),
                     bank["header_size"], bank["data_size"], formats))
    for name, table in data["strings"].items():
        rows.append("  %-32s count=%d" % (name, table["count"]))
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=os.environ.get(
        "WMMT6_DUMP", r"D:\Games\W6W-05"))
    parser.add_argument("--report")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--extract")
    parser.add_argument("--tone", type=int, default=0)
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.extract:
        row = extract(args.dump, args.extract, args.tone,
                      args.out or os.path.join("build", "tmp", "audio.wav"))
        print("extracted %s[%d]: %d Hz, %d ch, %d-bit, %d bytes" %
              (args.extract, args.tone, row["rate"], row["channels"],
               row["bits"], row["length"]))
        return 0

    data = collect(args.dump)
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)),
                    exist_ok=True)
        with open(args.report, "w", encoding="utf8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
    if args.list:
        print(report_text(data))
    else:
        print(report_text(data).splitlines()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
