"""Pack named values into std140 UBO buffers using exported GLSL bindings.

The reflected member offsets already encode std140 alignment; this module only
writes scalar, vec4 and mat4 values at those offsets. Missing members stay
zero. Dynamic-index cbuffer records have no std140 block and are rejected.
"""

import struct


def _encode(region, value):
    kind = region["kind"]
    if kind == "scalar":
        if value is None:
            value = 0
        if region["type"] == "float":
            return struct.pack("<f", float(value))
        if region["type"] == "uint":
            return struct.pack("<I", int(value) & 0xffffffff)
    elif kind == "vector":
        values = (0, 0, 0, 0) if value is None else tuple(value)
        if len(values) == 4:
            return struct.pack("<4f", *[float(item) for item in values])
    elif kind == "matrix":
        values = (0,) * 16 if value is None else tuple(value)
        if len(values) == 16:
            return struct.pack("<16f", *[float(item) for item in values])
    raise ValueError("unsupported std140 member %r" % region)


def pack_ubo(bindings, name, values=None):
    """Return one std140 UBO byte buffer for a named cbuffer block."""
    if not bindings["ubo"]:
        raise ValueError("shader uses dynamic cbuffer arrays, not std140 UBOs")
    block = next((item for item in bindings["cbuffers"]
                  if item["name"] == name), None)
    if block is None or not block["ubo"]:
        raise ValueError("no std140 UBO named %r" % name)
    values = values or {}
    out = bytearray(block["size"])
    for region in block["regions"]:
        raw = _encode(region, values.get(region["name"]))
        end = region["offset"] + len(raw)
        if len(raw) != region["size"] or end > len(out):
            raise ValueError("member %r outside UBO" % region["name"])
        out[region["offset"]:end] = raw
    return bytes(out)


def pack_ubos(bindings, values=None):
    """Return {cbuffer name: std140 bytes} for one shader stage."""
    values = values or {}
    return {block["name"]: pack_ubo(bindings, block["name"],
                                   values.get(block["name"], {}))
            for block in bindings["cbuffers"]}
