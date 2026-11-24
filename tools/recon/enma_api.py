"""Probe the exported Enma race-simulation DLL.

The shipped Wg6Enma_Release_IDL0.dll exports an MSVC-mangled C++ API with
complete type information. This tool reads the export table, calls the
enum-name helpers, and recovers SetDefault struct layouts by calling each
setter on differently poisoning buffers and comparing the results.

Raw output goes to docs/recon/ (gitignored): no game data is committed.
"""

import argparse
import ctypes
import json
import os
import re
import struct

DLL_NAME = "Wg6Enma_Release_IDL0.dll"


def exports(path):
    blob = open(path, "rb").read()
    pe = struct.unpack_from("<I", blob, 0x3C)[0]
    count = struct.unpack_from("<H", blob, pe + 6)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", blob, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)
    rva, _size = struct.unpack_from("<II", blob, dd)
    sec_table = opt + struct.unpack_from("<H", blob, pe + 20)[0]
    sections = []
    for i in range(count):
        at = sec_table + 40 * i
        virtual_size, virtual_at, raw_size, raw_at = struct.unpack_from(
            "<IIII", blob, at + 8)
        sections.append((virtual_at, virtual_size, raw_at))

    def offset(address):
        for virtual_at, virtual_size, raw_at in sections:
            if virtual_at <= address < virtual_at + virtual_size:
                return raw_at + address - virtual_at
        raise ValueError("unmapped RVA %x" % address)

    at = offset(rva)
    _chars, _base, _count, names, _funcs, name_table, _ords = \
        struct.unpack_from("<IIIIIII", blob, at + 12)
    result = []
    table = offset(name_table)
    for i in range(names):
        name_rva = struct.unpack_from("<I", blob, table + 4 * i)[0]
        result.append(blob[offset(name_rva):].split(b"\0")[0].decode("latin1"))
    return result


ENUM_RE = re.compile(r"^\?Get(E[A-Za-z0-9]+)Name@@YAPEBDW4\1@@@Z$")
DEFAULT_RE = re.compile(r"^\?SetDefault@(.+?)@@QEAAXXZ$")


def demangle_enum(name):
    m = ENUM_RE.match(name)
    return m.group(1) if m else None


def probe_enums(dll, names):
    result = {}
    for export in names:
        enum = demangle_enum(export)
        if not enum:
            continue
        func = getattr(dll, export)
        func.restype = ctypes.c_char_p
        func.argtypes = [ctypes.c_int]
        values = []
        misses = 0
        for i in range(512):
            try:
                raw = func(i)
            except Exception:
                break
            if not raw:
                misses += 1
                if misses >= 24:
                    break
                continue
            misses = 0
            values.append((i, raw.decode("latin1")))
        result[enum] = values
    return result


def probe_defaults(dll, names, size):
    result = {}
    for export in names:
        m = DEFAULT_RE.match(export)
        if not m:
            continue
        struct_name = m.group(1)
        func = getattr(dll, export)
        func.argtypes = [ctypes.c_void_p]
        passes = []
        for poison in (0xCC, 0x00, 0x55):
            buf = (ctypes.c_ubyte * size)(*([poison] * size))
            func(buf)
            passes.append(bytes(buf))
        written = [i for i in range(size)
                   if passes[0][i] == passes[1][i] == passes[2][i]]
        runs = []
        for i in written:
            if runs and runs[-1][1] == i:
                runs[-1][1] = i + 1
            else:
                runs.append([i, i + 1])
        result[struct_name] = {
            "max_written": max(written) + 1 if written else 0,
            "fields": [
                {"offset": begin, "size": end - begin,
                 "hex": passes[0][begin:end].hex()}
                for begin, end in runs
            ],
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--out", default="docs/recon/enma_api.json")
    parser.add_argument("--size", type=int, default=8192)
    args = parser.parse_args()

    dll_path = os.path.join(args.dump, DLL_NAME)
    names = exports(dll_path)
    dll = ctypes.CDLL(dll_path)
    data = {
        "dll": DLL_NAME,
        "exports": names,
        "enums": probe_enums(dll, names),
        "defaults": probe_defaults(dll, names, args.size),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf8") as handle:
        json.dump(data, handle, indent=1, ensure_ascii=False)
    print("exports=%d enums=%d structs=%d" %
          (len(names), len(data["enums"]), len(data["defaults"])))
    for enum, values in sorted(data["enums"].items()):
        sample = ", ".join("%d=%s" % pair for pair in values[:5])
        print("  %-18s %3d  %s" % (enum, len(values), sample))
    for name, info in sorted(data["defaults"].items()):
        print("  %-22s %4d bytes, %2d fields" %
              (name, info["max_written"], len(info["fields"])))


if __name__ == "__main__":
    main()
