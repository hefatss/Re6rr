"""Read a PE image without executing it and report the fields the port needs.

    python tools/recon/pe_report.py [--exe PATH] [--out DIR]

Writes <out>/pe.json and prints a short summary. Only the parts that matter for
a static recompiler are read: sections, imports, exception directory
(.pdata = one RUNTIME_FUNCTION per function), debug directory (PDB path),
relocations, TLS and the exported names.
"""

import argparse
import json
import os
import struct
import sys

IMAGE_SCN_MEM_EXECUTE = 0x20000000
IMAGE_SCN_CNT_CODE = 0x00000020


def u16(d, o):
    return struct.unpack_from("<H", d, o)[0]


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def u64(d, o):
    return struct.unpack_from("<Q", d, o)[0]


class PE:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.raw = f.read()
        d = self.raw
        if d[:2] != b"MZ":
            raise ValueError("not an MZ image")
        pe = u32(d, 0x3C)
        if d[pe:pe + 4] != b"PE\0\0":
            raise ValueError("no PE signature")
        self.pe = pe
        coff = pe + 4
        self.machine = u16(d, coff)
        self.section_count = u16(d, coff + 2)
        self.timestamp = u32(d, coff + 4)
        self.symbol_table = u32(d, coff + 8)
        self.symbol_count = u32(d, coff + 12)
        self.opt_size = u16(d, coff + 16)
        self.characteristics = u16(d, coff + 18)
        opt = coff + 20
        self.opt = opt
        self.magic = u16(d, opt)
        self.image_base = u64(d, opt + 24) if self.magic == 0x20B else u32(d, opt + 28)
        self.entry = u32(d, opt + 16)
        self.size_of_image = u32(d, opt + 56)
        self.size_of_headers = u32(d, opt + 60)
        self.subsystem = u16(d, opt + 68)
        # data directories start at opt+112 for PE32+, opt+96 for PE32
        dd = opt + (112 if self.magic == 0x20B else 96)
        self.dirs = [(u32(d, dd + 8 * i), u32(d, dd + 8 * i + 4)) for i in range(16)]
        self.sections = []
        sec = opt + self.opt_size
        for i in range(self.section_count):
            o = sec + 40 * i
            name = d[o:o + 8].rstrip(b"\0").decode("latin1")
            self.sections.append({
                "name": name,
                "vsize": u32(d, o + 8),
                "vaddr": u32(d, o + 12),
                "raw_size": u32(d, o + 16),
                "raw_ptr": u32(d, o + 20),
                "characteristics": u32(d, o + 36),
            })

    # ---- helpers ----
    def off(self, rva):
        for s in self.sections:
            lo = s["vaddr"]
            hi = lo + max(s["vsize"], s["raw_size"])
            if lo <= rva < hi:
                delta = rva - lo
                if delta >= s["raw_size"]:
                    return None
                return s["raw_ptr"] + delta
        return None

    def cstr(self, rva, limit=512):
        o = self.off(rva)
        if o is None:
            return None
        end = self.raw.find(b"\0", o, o + limit)
        if end < 0:
            return None
        return self.raw[o:end].decode("latin1", "replace")

    def section_of(self, rva):
        for s in self.sections:
            if s["vaddr"] <= rva < s["vaddr"] + max(s["vsize"], s["raw_size"]):
                return s["name"]
        return None

    # ---- directories ----
    def imports(self):
        rva, size = self.dirs[1]
        out = []
        if not rva:
            return out
        o = self.off(rva)
        if o is None:
            return out
        idx = 0
        while True:
            desc = o + 20 * idx
            ilt = u32(self.raw, desc)
            name_rva = u32(self.raw, desc + 12)
            iat = u32(self.raw, desc + 16)
            if not (ilt or name_rva or iat):
                break
            dll = self.cstr(name_rva) or ""
            funcs = []
            tbl = self.off(ilt or iat)
            if tbl is not None:
                step = 8 if self.magic == 0x20B else 4
                j = 0
                while True:
                    val = u64(self.raw, tbl + step * j) if step == 8 else u32(self.raw, tbl + step * j)
                    if not val:
                        break
                    if val & (1 << (step * 8 - 1)):
                        funcs.append({"ordinal": val & 0xFFFF})
                    else:
                        funcs.append({"name": self.cstr((val & 0x7FFFFFFF) + 2) or ""})
                    j += 1
            out.append({"dll": dll, "functions": funcs})
            idx += 1
        return out

    def exports(self):
        rva, size = self.dirs[0]
        if not rva:
            return []
        o = self.off(rva)
        if o is None:
            return []
        count = u32(self.raw, o + 24)
        names_rva = u32(self.raw, o + 32)
        out = []
        no = self.off(names_rva)
        if no is None:
            return out
        for i in range(min(count, 4096)):
            nrva = u32(self.raw, no + 4 * i)
            n = self.cstr(nrva)
            if n:
                out.append(n)
        return out

    def pdata(self):
        rva, size = self.dirs[3]
        if not rva or not size:
            return {"count": 0, "note": "no exception directory"}
        count = size // 12
        o = self.off(rva)
        entries = []
        if o is not None:
            for i in range(count):
                begin, end, unwind = struct.unpack_from("<III", self.raw, o + 12 * i)
                if begin == 0:
                    continue
                entries.append({"begin": begin, "end": end, "unwind": unwind})
        entries.sort(key=lambda e: e["begin"])
        # functions are RVA-sorted; report merge candidates (shared unwind records)
        return {
            "count": len(entries),
            "rva_min": entries[0]["begin"] if entries else None,
            "rva_max": entries[-1]["end"] if entries else None,
            "unique_unwind": len({e["unwind"] for e in entries}),
            "entry_size": max((e["end"] - e["begin"]) for e in entries) if entries else 0,
            "entries_head": entries[:8],
        }

    def debug(self):
        rva, size = self.dirs[6]
        out = {"pdb": None, "types": []}
        if not rva:
            return out
        o = self.off(rva)
        if o is None:
            return out
        for i in range(size // 28):
            d = o + 28 * i
            kind = u32(self.raw, d + 12)
            addr = u32(self.raw, d + 20)
            out["types"].append(kind)
            if kind == 2:  # CODEVIEW
                p = self.off(addr)
                if p is not None and self.raw[p:p + 4] == b"RSDS":
                    guid = self.raw[p + 4:p + 20].hex()
                    age = u32(self.raw, p + 20)
                    end = self.raw.find(b"\0", p + 24)
                    out["pdb"] = {"guid": guid, "age": age, "path": self.raw[p + 24:end].decode("latin1")}
        return out

    def relocations(self):
        rva, size = self.dirs[5]
        if not rva:
            return {"blocks": 0, "entries": 0}
        o = self.off(rva)
        if o is None:
            return {"blocks": 0, "entries": 0}
        blocks = entries = 0
        p = o
        end = o + size
        while p + 8 <= end:
            page = u32(self.raw, p)
            bsize = u32(self.raw, p + 4)
            if bsize < 8:
                break
            entries += max(0, (bsize - 8) // 2)
            blocks += 1
            p += bsize
            if not page:
                break
        return {"blocks": blocks, "entries": entries}

    def tls(self):
        rva, size = self.dirs[9]
        if not rva:
            return None
        o = self.off(rva)
        if o is None:
            return None
        if self.magic == 0x20B:
            start, end, index, callbacks = struct.unpack_from("<QQQQ", self.raw, o)
        else:
            start, end, index, callbacks = struct.unpack_from("<IIII", self.raw, o)
        cbs = []
        co = self.off(callbacks - self.image_base) if callbacks else None
        if co is not None:
            step = 8 if self.magic == 0x20B else 4
            for i in range(16):
                v = u64(self.raw, co + step * i) if step == 8 else u32(self.raw, co + step * i)
                if not v:
                    break
                cbs.append(hex(v))
        return {"callbacks": cbs, "raw_start": hex(start), "raw_end": hex(end)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=r"D:\Games\W6W-05\wmn6r.exe")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "recon"))
    args = ap.parse_args()

    pe = PE(args.exe)
    rep = {
        "path": os.path.abspath(args.exe),
        "size": len(pe.raw),
        "sha256": __import__("hashlib").sha256(pe.raw).hexdigest(),
        "machine": hex(pe.machine),
        "magic": hex(pe.magic),
        "timestamp": pe.timestamp,
        "image_base": hex(pe.image_base),
        "entry_rva": hex(pe.entry),
        "size_of_image": pe.size_of_image,
        "symbols": {"table": pe.symbol_table, "count": pe.symbol_count},
        "sections": pe.sections,
        "directories": [{"index": i, "rva": hex(r), "size": s} for i, (r, s) in enumerate(pe.dirs) if r or s],
        "imports": pe.imports(),
        "exports": pe.exports()[:512],
        "pdata": pe.pdata(),
        "debug": pe.debug(),
        "relocations": pe.relocations(),
        "tls": pe.tls(),
    }
    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, "pe.json")
    with open(dst, "w", encoding="utf8") as f:
        json.dump(rep, f, indent=1)

    print("exe      :", rep["path"], rep["size"], "bytes")
    print("sha256   :", rep["sha256"])
    print("machine  :", rep["machine"], "image_base", rep["image_base"], "entry", rep["entry_rva"])
    print("sections :", ", ".join("%s %d" % (s["name"], s["raw_size"]) for s in rep["sections"]))
    print("pdata    :", rep["pdata"]["count"], "functions,", rep["pdata"].get("unique_unwind"), "unwind records")
    print("imports  :", len(rep["imports"]), "dlls,", sum(len(i["functions"]) for i in rep["imports"]), "symbols")
    print("exports  :", len(rep["exports"]))
    print("pdb      :", (rep["debug"]["pdb"] or {}).get("path"))
    print("relocs   :", rep["relocations"])
    print("tls      :", rep["tls"])
    print("wrote    :", dst)


if __name__ == "__main__":
    sys.exit(main())
