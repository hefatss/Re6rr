"""Probe CGameInput field offsets and drive yt::CSeq via the Enma DLL.

Used only for reconstruction; raw results land in docs/recon/ (gitignored).
"""

import argparse
import ctypes
import json
import os
import struct

DLL_NAME = "Wg6Enma_Release_IDL0.dll"
SIZE = 4096


def load(dump):
    return ctypes.CDLL(os.path.join(dump, DLL_NAME))


def probe_getters(dll):
    getters = {
        "accel": "?getAccel@CGameInput@@QEBAMXZ",
        "brake": "?getBrake@CGameInput@@QEBAMXZ",
        "steer": "?getSteer@CGameInput@@QEBAMXZ",
        "gear": "?getGear@CGameInput@@QEBAHXZ",
        "intrusion": "?isIntrusion@CGameInput@@QEBA_NXZ",
        "view_change": "?isViewChange@CGameInput@@QEBA_NXZ",
    }
    result = {}
    for label, export in getters.items():
        func = getattr(dll, export)
        if label == "gear":
            func.restype, func.argtypes = ctypes.c_int, [ctypes.c_void_p]
        elif label in ("intrusion", "view_change"):
            func.restype, func.argtypes = ctypes.c_bool, [ctypes.c_void_p]
        else:
            func.restype, func.argtypes = ctypes.c_float, [ctypes.c_void_p]
        baseline_buf = (ctypes.c_ubyte * SIZE)()
        baseline = func(baseline_buf)
        hits = []
        for offset in range(0, 256, 4):
            buf = (ctypes.c_ubyte * SIZE)()
            struct.pack_into("<f", buf, offset, float(offset + 1))
            value = func(buf)
            if value != baseline:
                hits.append({"offset": offset, "value": value})
        result[label] = {"export": export, "baseline": baseline, "hits": hits}
    return result


def probe_default_config(dll):
    setter = getattr(dll, "?SetDefault@SConfigPlay@@QEAAXXZ")
    setter.argtypes = [ctypes.c_void_p]
    buf = (ctypes.c_ubyte * SIZE)()
    setter(buf)
    return bytes(buf)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", required=True)
    parser.add_argument("--out", default="docs/recon/enma_sim.json")
    args = parser.parse_args()

    dll = load(args.dump)
    data = {
        "getters": probe_getters(dll),
        "config_default_hex": probe_default_config(dll).hex(),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf8") as handle:
        json.dump(data, handle, indent=1)
    for label, info in data["getters"].items():
        print("%-12s base=%-8s hits=%s" %
              (label, info["baseline"],
               ", ".join("%d:%s" % (h["offset"], h["value"])
                         for h in info["hits"][:8])))
    print("config bytes", len(data["config_default_hex"]) // 2)


if __name__ == "__main__":
    main()
