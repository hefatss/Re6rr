"""Run the freestanding engine core against the real dump.

    python tools/engine/test_engine.py [--dump DIR] [--dll PATH]

Two groups of checks:

  lua     the C host loads the same scripts as tools/lua/lua_probe.py and must
          return the same values through the native -> Lua protocol.
  assets  the C XMD/NDWD/NTWD parsers must agree with the Python parsers in
          tools/assets on every file sampled from the dump.

The C core is a normal DLL; ctypes drives it the way the Android platform layer
will.
"""

import argparse
import collections
import ctypes
import gzip
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "lua"))
sys.path.insert(0, os.path.join(ROOT, "tools", "assets"))

from lua_host import LuaHost  # noqa: E402
import glsl_ubo  # noqa: E402
import ndwd_records  # noqa: E402
import nsxr_shader  # noqa: E402
import ntwd_texture  # noqa: E402
import nut_texture  # noqa: E402
from xmd_streams import load, parse as xmd_parse  # noqa: E402

R6_OK = 0
R6_ERR_ARG = -1
R6_ERR_FORMAT = -5
R6_ERR_BUFFER = -6
R6_ERR_NOT_FOUND = -7

LOG_FN = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int,
                          ctypes.c_char_p, ctypes.c_size_t)


class Config(ctypes.Structure):
    _fields_ = [
        ("log", LOG_FN),
        ("log_user", ctypes.c_void_p),
        ("arena", ctypes.c_void_p),
        ("arena_size", ctypes.c_size_t),
    ]


class Stream(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32), ("size", ctypes.c_uint32)]


class NdwdHeader(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("version", ctypes.c_uint16),
        ("group_count", ctypes.c_uint16),
        ("section_size", ctypes.c_uint32 * 4),
    ]


class NdwdGroup(ctypes.Structure):
    _fields_ = [
        ("offset", ctypes.c_uint32),
        ("name_offset", ctypes.c_uint32),
        ("subrecord_count", ctypes.c_uint16),
        ("subrecord_start", ctypes.c_uint32),
    ]


class NtwdHeader(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint8),
        ("texture_count", ctypes.c_uint16),
    ]


class NtwdTexture(ctypes.Structure):
    _fields_ = [
        ("header_offset", ctypes.c_uint32),
        ("data_offset", ctypes.c_uint32),
        ("data_size", ctypes.c_uint32),
        ("texture_id", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("width", ctypes.c_uint16),
        ("height", ctypes.c_uint16),
        ("header_stride", ctypes.c_uint16),
        ("faces", ctypes.c_uint8),
        ("format", ctypes.c_uint8),
    ]


class GlslRegion(ctypes.Structure):
    _fields_ = [
        ("offset", ctypes.c_uint32),
        ("size", ctypes.c_uint32),
        ("kind", ctypes.c_uint8),
        ("type", ctypes.c_uint8),
    ]


class GlslValue(ctypes.Union):
    _fields_ = [
        ("f", ctypes.c_float),
        ("u", ctypes.c_uint32),
        ("v", ctypes.c_float * 4),
        ("m", ctypes.c_float * 16),
    ]


class ScriptSource(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
    ]


def load_core(dll, dump):
    """Preload lua5.1.dll so the freestanding core resolves its imports."""
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(dump)
    ctypes.CDLL(os.path.join(dump, "lua5.1.dll"))
    return ctypes.CDLL(dll)


class Engine:
    def __init__(self, dll, dump):
        self.lib = load_core(dll, dump)
        lib = self.lib
        lib.r6_engine_size.restype = ctypes.c_size_t
        lib.r6_engine_init.restype = ctypes.c_void_p
        lib.r6_engine_init.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(Config)]
        lib.r6_engine_shutdown.argtypes = [ctypes.c_void_p]
        lib.r6_engine_load_script.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                              ctypes.c_void_p, ctypes.c_size_t]
        lib.r6_engine_set_setting_const.argtypes = [ctypes.c_void_p]
        lib.r6_engine_has_function.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.r6_engine_call_vec3_key.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_float)]
        lib.r6_engine_call_vec3_index.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_float)]
        lib.r6_engine_call_number.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double)]
        lib.r6_engine_last_error.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                             ctypes.c_size_t]
        lib.r6_engine_load_context.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ScriptSource), ctypes.c_size_t]
        self.size = lib.r6_engine_size()
        self.storage = ctypes.create_string_buffer(self.size)
        self.messages = []
        self.log = LOG_FN(self._on_log)
        self.config = Config(self.log, None, None, 0)
        self.handle = lib.r6_engine_init(self.storage, self.size,
                                         ctypes.byref(self.config))
        if not self.handle:
            raise RuntimeError("r6_engine_init failed: %s" % self.error())

    def _on_log(self, user, level, message, length):
        self.messages.append(message[:length].decode("utf-8", "replace"))

    def close(self):
        if self.handle:
            self.lib.r6_engine_shutdown(self.handle)
            self.handle = None

    def error(self):
        buf = ctypes.create_string_buffer(256)
        self.lib.r6_engine_last_error(self.handle, buf, len(buf))
        return buf.value.decode("utf-8", "replace")

    def load(self, path):
        data = open(path, "rb").read()
        rc = self.lib.r6_engine_load_script(self.handle,
                                            os.path.basename(path).encode(),
                                            data, len(data))
        if rc != R6_OK:
            raise RuntimeError("%s: %s" % (path, self.error()))

    def context(self, paths):
        blobs = [open(p, "rb").read() for p in paths]
        guards = [ctypes.create_string_buffer(b, len(b)) for b in blobs]
        sources = (ScriptSource * len(paths))()
        for i, path in enumerate(paths):
            sources[i].name = os.path.basename(path).encode()
            sources[i].data = ctypes.cast(guards[i], ctypes.c_void_p)
            sources[i].size = len(blobs[i])
        rc = self.lib.r6_engine_load_context(self.handle, sources, len(paths))
        return rc, self.error()

    def setting_const(self):
        rc = self.lib.r6_engine_set_setting_const(self.handle)
        assert rc == R6_OK, rc

    def has(self, name):
        return bool(self.lib.r6_engine_has_function(self.handle,
                                                    name.encode()))

    def vec3_key(self, name, key, index):
        out = (ctypes.c_float * 3)()
        rc = self.lib.r6_engine_call_vec3_key(self.handle, name.encode(),
                                              key.encode(), index, out)
        return rc, list(out)

    def vec3_index(self, name, index):
        out = (ctypes.c_float * 3)()
        rc = self.lib.r6_engine_call_vec3_index(self.handle, name.encode(),
                                               index, out)
        return rc, list(out)

    def number(self, name):
        out = ctypes.c_double()
        rc = self.lib.r6_engine_call_number(self.handle, name.encode(),
                                            ctypes.byref(out))
        return rc, out.value


def same_vec3(a, b, tol=1e-4):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_lua(dll, dump, failures):
    tire_define = os.path.join(dump, "data", "car", "tire", "script",
                               "TireDefine.lua")
    car_pos = os.path.join(dump, "data", "car", "position", "pos",
                           "getTirePos_CRC_928GT_Masaki.lua")
    library = os.path.join(dump, "data", "car", "color", "LibraryColor.lua")
    car = "CRC_928GT_Masaki"
    bad_path = os.path.join(HERE, ".bad_chunk.lua")
    with open(bad_path, "w", encoding="ascii") as f:
        f.write("this is not lua\n")

    engine = Engine(dll, dump)
    try:
        engine.setting_const()
        for path in (tire_define, car_pos):
            engine.load(path)
        if not engine.has("GetTirePos"):
            failures.append("lua: GetTirePos missing after load")
            return
        rc, got = engine.vec3_key("GetTirePos", car, 0)
        if rc != R6_OK:
            failures.append("lua: GetTirePos rc=%d %s" % (rc, engine.error()))
            return
        with LuaHost(os.path.join(dump, "lua5.1.dll")) as host:
            host.set_table("SettingConst", {
                "Locale": {"Japan": 0}, "Language": {"Japanese": 0},
                "Difficult": {"Normal": 2}, "NetworkMode": {"Disable": 0},
                "NetworkID": {"NetworkID_0": 0},
                "ForceFeedBackLevel": {"Disable": 0}, "State": {"Enable": 1},
            })
            host.load_file(tire_define)
            host.load_file(car_pos)
            want = list(host.call_vec3("GetTirePos", car, 0))
        if not same_vec3(got, want):
            failures.append("lua: GetTirePos C=%s python=%s" % (got, want))
        else:
            print("  GetTirePos(%r, 0) = (%.6f, %.6f, %.6f)" % tuple([car] + got))

        # Index-only form uses the same protocol with one argument.
        engine.load(library)
        rc, color = engine.number("ColorMax")
        if rc != R6_OK or abs(color - 250.0) > 1e-9:
            failures.append("lua: ColorMax rc=%d value=%s" % (rc, color))
        else:
            print("  ColorMax() = %.0f" % color)

        rc, spec_value = engine.number("GetHorsepower1st")
        if rc != R6_ERR_NOT_FOUND or spec_value != 0.0:
            failures.append("lua: missing scalar did not zero the result")
        else:
            print("  missing scalar reports: %s" % engine.error())

        spec = os.path.join(dump, "data", "car", "specification",
                            "PLC_928GT_Specification.lua")
        engine.load(spec)
        rc, horsepower = engine.number("GetHorsepower1st")
        if rc != R6_OK or abs(horsepower - 330.0) > 1e-9:
            failures.append("lua: GetHorsepower1st rc=%d value=%s"
                            % (rc, horsepower))
        else:
            print("  GetHorsepower1st() = %.0f" % horsepower)

        lib = engine.lib
        set_number = lib.r6_engine_set_number
        set_number.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                               ctypes.c_double]
        rc = set_number(engine.handle, b"TestValue", 42.0)
        tiny = b"function GetTestValue() return TestValue end"
        rc2 = lib.r6_engine_load_script(engine.handle, b"test_value.lua",
                                        tiny, len(tiny))
        rc3, value = engine.number("GetTestValue")
        if rc != R6_OK or rc2 != R6_OK or rc3 != R6_OK or value != 42.0:
            failures.append("lua: set_number rc=%d/%d/%d value=%s"
                            % (rc, rc2, rc3, value))
        else:
            print("  set_number: GetTestValue() = %.0f" % value)

        rc, zeros = engine.vec3_key("NoSuchFunction", car, 0)
        if rc != R6_ERR_NOT_FOUND or "NoSuchFunction" not in engine.error():
            failures.append("lua: missing function did not report properly")
        elif zeros != [0.0, 0.0, 0.0]:
            failures.append("lua: missing function did not zero the vector")
        else:
            print("  missing function reports: %s" % engine.error())

        # Ordered context bundle: same protocol the engine uses per car.
        other = Engine(dll, dump)
        try:
            other.setting_const()
            rc, message = other.context([tire_define, car_pos])
            if rc != R6_OK or not other.has("GetTirePos"):
                failures.append("lua: context load rc=%d %s" % (rc, message))
            else:
                with LuaHost(os.path.join(dump, "lua5.1.dll")) as host:
                    host.set_table("SettingConst", {})
                    host.load_file(tire_define)
                    host.load_file(car_pos)
                    want = list(host.call_vec3("GetTirePos", car, 0))
                rc, got = other.vec3_key("GetTirePos", car, 0)
                if rc != R6_OK or not same_vec3(got, want):
                    failures.append("lua: context GetTirePos C=%s py=%s"
                                    % (got, want))
                else:
                    print("  context bundle reproduces GetTirePos")

            # A failing script stops the bundle in order.
            rc, message = other.context([car_pos, bad_path])
            if rc == R6_OK:
                failures.append("lua: context accepted a broken script")
            else:
                print("  context stops at broken script: rc=%d" % rc)
        finally:
            other.close()

        # A script error must surface as a clean failure, not a crash.
        try:
            engine.load(bad_path)
            failures.append("lua: bad chunk was accepted")
        except RuntimeError as exc:
            print("  bad chunk rejected: %s" % str(exc).split(":")[-1].strip())

        if not any("engine ready" in m for m in engine.messages):
            failures.append("lua: log callback never fired")
    finally:
        engine.close()
        os.remove(bad_path)


def test_gzip(dll, dump, failures):
    lib = load_core(dll, dump)
    lib.r6_gzip_expected_size.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.POINTER(ctypes.c_size_t)]
    lib.r6_gzip_inflate.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_size_t)]
    samples = []
    for base, _dirs, files in os.walk(os.path.join(dump, "data")):
        for name in files:
            low = name.lower()
            if low.endswith((".tex", ".mdl")):
                samples.append(os.path.join(base, name))
    samples.sort()
    checked = 0
    for path in samples:
        raw = open(path, "rb").read()
        if raw[:3] != b"\x1f\x8b\x08":
            continue
        want = gzip.decompress(raw)
        src = ctypes.create_string_buffer(raw, len(raw))
        size = ctypes.c_size_t()
        rc = lib.r6_gzip_expected_size(src, len(raw), ctypes.byref(size))
        if rc != R6_OK or size.value != len(want):
            failures.append("gzip: %s expected rc=%d size=%d py=%d" % (
                path, rc, size.value, len(want)))
            break

        small = ctypes.create_string_buffer(16)
        need = ctypes.c_size_t()
        rc = lib.r6_gzip_inflate(src, len(raw), small, 16, ctypes.byref(need))
        if rc != R6_ERR_BUFFER or need.value != len(want):
            failures.append("gzip: %s small buffer rc=%d need=%d" % (
                path, rc, need.value))
            break

        dst = ctypes.create_string_buffer(len(want))
        got_size = ctypes.c_size_t()
        rc = lib.r6_gzip_inflate(src, len(raw), dst, len(want),
                                 ctypes.byref(got_size))
        got = dst.raw[:got_size.value]
        if rc != R6_OK or got != want:
            failures.append("gzip: %s inflate rc=%d size=%d py=%d" % (
                path, rc, got_size.value, len(want)))
            break
        checked += 1
        if checked >= 20:
            break
    print("  gzip: %d streams byte-identical to Python gzip" % checked)
    if checked == 0:
        failures.append("gzip: no compressed samples found")

    corrupted = b"\x1f\x8b\x08\x00" + samples[0].encode()[:4]
    src = ctypes.create_string_buffer(corrupted, len(corrupted))
    size = ctypes.c_size_t()
    rc = lib.r6_gzip_expected_size(src, len(corrupted), ctypes.byref(size))
    if rc == R6_OK:
        failures.append("gzip: malformed header accepted")


def decompress(path):
    data = open(path, "rb").read()
    if data[:3] == b"\x1f\x8b\x08":
        data = gzip.decompress(data)
    return data


def test_assets(dll, dump, failures, limit):
    lib = load_core(dll, dump)
    lib.r6_xmd_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.POINTER(Stream), ctypes.c_size_t,
                                 ctypes.POINTER(ctypes.c_uint32),
                                 ctypes.POINTER(ctypes.c_uint32)]
    lib.r6_ndwd_parse_header.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                         ctypes.POINTER(NdwdHeader)]
    lib.r6_ndwd_parse_group.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.POINTER(NdwdHeader),
                                        ctypes.c_uint32,
                                        ctypes.POINTER(NdwdGroup)]
    lib.r6_ntwd_parse.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(NtwdHeader),
                                  ctypes.POINTER(NtwdTexture),
                                  ctypes.c_size_t]

    tex = []
    mdl = []
    for base, _dirs, files in os.walk(os.path.join(dump, "data")):
        for name in files:
            low = name.lower()
            if low.endswith(".tex"):
                tex.append(os.path.join(base, name))
            elif low.endswith(".mdl"):
                mdl.append(os.path.join(base, name))
    tex.sort()
    mdl.sort()
    tex = tex[:limit]
    mdl = mdl[:limit]

    n_tex = 0
    n_stream = 0
    for path in tex:
        data = decompress(path)
        buf = ctypes.create_string_buffer(data, len(data))
        version = ctypes.c_uint32()
        count = ctypes.c_uint32()
        rc = lib.r6_xmd_parse(buf, len(data), None, 0, ctypes.byref(version),
                              ctypes.byref(count))
        if rc == R6_ERR_BUFFER:
            table = (Stream * count.value)()
            rc = lib.r6_xmd_parse(buf, len(data), table, count.value,
                                  ctypes.byref(version), ctypes.byref(count))
        else:
            table = None
        _, offsets = xmd_parse(data)
        if rc != R6_OK or count.value != len(offsets):
            failures.append("assets: %s xmd rc=%d count=%s py=%d" % (
                path, rc, count.value, len(offsets)))
            continue
        for i, start in enumerate(offsets):
            if table[i].offset != start:
                failures.append("assets: %s stream %d offset" % (path, i))
                break
            probe = data[start:start + 4]
            if probe == b"NTWD":
                stream = data[start:start + table[i].size]
                s = ctypes.create_string_buffer(stream, len(stream))
                header = NtwdHeader()
                rc = lib.r6_ntwd_parse(s, len(stream), ctypes.byref(header),
                                       None, 0)
                if rc == R6_ERR_BUFFER:
                    textures = (NtwdTexture * header.texture_count)()
                    rc = lib.r6_ntwd_parse(s, len(stream), ctypes.byref(header),
                                           textures, header.texture_count)
                else:
                    textures = None
                if rc != R6_OK:
                    failures.append("assets: %s stream %d ntwd rc=%d" % (
                        path, i, rc))
                    continue
                want = ntwd_texture.parse_stream(stream)
                if header.texture_count != want["count"]:
                    failures.append("assets: %s stream %d count" % (path, i))
                    continue
                for t, w in zip(textures, want["textures"]):
                    got = (t.texture_id, t.width, t.height, t.faces, t.format,
                           t.flags, t.data_offset, t.data_size,
                           t.header_stride, t.header_offset)
                    exp = (w["hash"], w["width"], w["height"], w["faces"],
                           w["fmt"], w["flags"], w["data_off"],
                           w["data_size"], w["stride"], w["header"])
                    if got != exp:
                        failures.append("assets: %s stream %d tex %d\n"
                                        "    C=%s\n    py=%s" % (
                                            path, i, w["index"], got, exp))
                        break
                n_stream += 1
                n_tex += header.texture_count
    print("  textures: %d files, %d streams, %d texture headers match" % (
        len(tex), n_stream, n_tex))

    n_group = 0
    for path in mdl:
        data = decompress(path)
        buf = ctypes.create_string_buffer(data, len(data))
        _, offsets = xmd_parse(data)
        for i, start in enumerate(offsets):
            end = offsets[i + 1] if i + 1 < len(offsets) else len(data)
            stream = data[start:end]
            if stream[:4] != b"NDWD":
                continue
            s = ctypes.create_string_buffer(stream, len(stream))
            header = NdwdHeader()
            rc = lib.r6_ndwd_parse_header(s, len(stream), ctypes.byref(header))
            want = ndwd_records.stream_info(stream)
            if rc != R6_OK:
                failures.append("assets: %s stream %d ndwd rc=%d" % (
                    path, i, rc))
                continue
            got = (header.id, header.version, header.group_count,
                   list(header.section_size))
            exp = (want["id"], want["version"], want["group_count"],
                   list(want["sizes"]))
            if got != exp:
                failures.append("assets: %s stream %d header C=%s py=%s" % (
                    path, i, got, exp))
                continue
            for gi, group in enumerate(want["groups"]):
                out = NdwdGroup()
                rc = lib.r6_ndwd_parse_group(s, len(stream),
                                             ctypes.byref(header), gi,
                                             ctypes.byref(out))
                got = (out.name_offset, out.subrecord_count,
                       out.subrecord_start)
                exp = (group["name_off"], group["nsub"], group["sub_start"])
                if rc != R6_OK or got != exp:
                    failures.append("assets: %s stream %d group %d C=%s py=%s"
                                    % (path, i, gi, got, exp))
                    break
                n_group += 1
    print("  meshes: %d files, %d NDWD groups match" % (len(mdl), n_group))


def test_nut_decode(dll, dump, failures):
    """C BC1/BC2/BC3/RGBA8 decode must match the Python CPU decoder."""
    lib = load_core(dll, dump)
    lib.r6_nut_decode_rgba.restype = ctypes.c_int
    lib.r6_nut_decode_rgba.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(NtwdTexture),
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t)]

    def compare(raw, entry, level, face, label):
        expected = nut_texture.decode_entry(raw, entry, level, face)
        texture = NtwdTexture(
            header_offset=entry["header"], data_offset=entry["data_offset"],
            data_size=entry["data_size"], flags=entry["flags"],
            width=entry["width"], height=entry["height"],
            faces=entry["levels"], format=entry["format"])
        source = ctypes.create_string_buffer(raw, len(raw))
        output = ctypes.create_string_buffer(len(expected))
        written = ctypes.c_size_t()
        rc = lib.r6_nut_decode_rgba(source, len(raw), ctypes.byref(texture),
                                    level, face, output, len(expected),
                                    ctypes.byref(written))
        if rc != R6_OK or written.value != len(expected) or \
                output.raw != expected:
            failures.append("nut decode: %s rc=%d size=%d/%d" % (
                label, rc, written.value, len(expected)))
            return
        short = ctypes.create_string_buffer(max(1, len(expected) - 1))
        rc = lib.r6_nut_decode_rgba(source, len(raw), ctypes.byref(texture),
                                    level, face, short, len(expected) - 1,
                                    ctypes.byref(written))
        if rc != R6_ERR_BUFFER or written.value != len(expected):
            failures.append("nut decode buffer: %s rc=%d size=%d" % (
                label, rc, written.value))

    cases = [
        ("data/car/numberPlate/flame/flame_illumination1_c1.nut", 0, 0, 0),
        ("data/course/stage/A_FUKUOKA_DAY_NML/FUKUOKA/model/nut/"
         "FUKUOKA_DAY_NML_Tex1.nut", 0, 0, 0),
        ("data/course/stage/A_FUKUOKA_DAY_NML/FUKUOKA/model/nut/"
         "FUKUOKA_DAY_NML_Tex1.nut", 4, 0, 1),
        ("data/car/car_data/otherCar/OTH_NZE121.nut", 0, 0, 0),
        ("data/car/blend/blend_system.nut", 0, 0, 0),
        ("data_jp/flash/DRIVE/ghost_battle/"
         "B073_02_01_DRESSUP_SEL00.nut", 12, 0, 0),
    ]
    for relative, index, level, face in cases:
        path = os.path.join(dump, *relative.split("/"))
        raw = nut_texture.read_nut(path)
        compare(raw, nut_texture.parse_entries(raw)[index], level, face,
                "%s #%d face=%d" % (relative, index, face))

    quota = collections.Counter()
    paths = []
    for base, _, files in os.walk(dump):
        for name in files:
            if name.lower().endswith(".nut"):
                paths.append(os.path.join(base, name))
    paths.sort()
    for path in paths:
        raw = nut_texture.read_nut(path)
        for index, entry in enumerate(nut_texture.parse_entries(raw)):
            name = entry["format_name"]
            if name not in ("BC1", "BC2", "BC3", "ARGB8", "A8R8G8B8") or \
                    entry["cube"] or \
                    entry["width"] * entry["height"] > 65536 or \
                    quota[name] >= 32:
                continue
            quota[name] += 1
            compare(raw, entry, 0, 0, "%s #%d" % (
                os.path.relpath(path, dump), index))
    bad_format = NtwdTexture(
        header_offset=0, data_offset=0, data_size=16, flags=0,
        width=4, height=4, faces=1, format=0x7f)
    source = ctypes.create_string_buffer(16)
    output = ctypes.create_string_buffer(64)
    written = ctypes.c_size_t()
    rc = lib.r6_nut_decode_rgba(source, 16, ctypes.byref(bad_format), 0, 0,
                                output, 64, ctypes.byref(written))
    if rc != R6_ERR_FORMAT:
        failures.append("nut decode format: rc=%d" % rc)
    print("  nut pixel decode: %d sampled textures, cube face, buffer checks" %
          (len(cases) + sum(quota.values())))


def test_glsl_ubo(dll, dump, failures):
    """C std140 packing must match the Python reference byte-for-byte."""
    lib = load_core(dll, dump)
    lib.r6_glsl_pack_ubo.restype = ctypes.c_int
    lib.r6_glsl_pack_ubo.argtypes = [
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(GlslRegion),
        ctypes.POINTER(GlslValue), ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t)]
    body = nsxr_shader.parse_nsh(
        os.path.join(dump, nsxr_shader.SHADER_DIR, "Body.nsh"))
    pixel = nsxr_shader.glsl_bindings(body["records"][1])
    vertex = nsxr_shader.glsl_bindings(body["records"][0])
    kinds = {"scalar": 0, "vector": 1, "matrix": 2}
    types = {"float": 0, "uint": 1}

    def compare(bindings, block_name, values, label):
        block = next(item for item in bindings["cbuffers"]
                     if item["name"] == block_name)
        regions = (GlslRegion * len(block["regions"]))()
        packed = (GlslValue * len(block["regions"]))()
        for index, region in enumerate(block["regions"]):
            regions[index] = GlslRegion(
                offset=region["offset"], size=region["size"],
                kind=kinds[region["kind"]], type=types[region["type"]])
            value = values.get(region["name"])
            if region["kind"] == "scalar":
                if region["type"] == "uint":
                    packed[index].u = int(value or 0)
                else:
                    packed[index].f = float(value or 0)
            else:
                count = 16 if region["kind"] == "matrix" else 4
                source = value or (0,) * count
                target = packed[index].m if count == 16 else packed[index].v
                for part in range(count):
                    target[part] = float(source[part])
        output = ctypes.create_string_buffer(block["size"])
        written = ctypes.c_size_t()
        rc = lib.r6_glsl_pack_ubo(output, block["size"], regions, packed,
                                  len(regions), ctypes.byref(written))
        expected = glsl_ubo.pack_ubo(bindings, block_name, values)
        if rc != R6_OK or written.value != block["size"] or \
                output.raw != expected:
            failures.append("glsl ubo: %s rc=%d size=%d" %
                            (label, rc, written.value))
        return regions, packed

    alpha_values = {"AlphaTestRef": 0.25, "AlphaTestFunc": 7}
    alpha_regions, alpha_packed = compare(pixel, "AlphaTest", alpha_values,
                                          "AlphaTest")
    custom_values = {
        region["name"]: tuple(index + part for part in range(4))
        for index, region in enumerate(next(
            item for item in pixel["cbuffers"]
            if item["name"] == "CustomParameter")["regions"])
    }
    compare(pixel, "CustomParameter", custom_values, "CustomParameter")
    per_draw_values = {
        region["name"]: tuple(index * 16 + part for part in range(16))
        for index, region in enumerate(next(
            item for item in vertex["cbuffers"]
            if item["name"] == "PerDraw")["regions"])
    }
    compare(vertex, "PerDraw", per_draw_values, "PerDraw")

    short = ctypes.create_string_buffer(4)
    written = ctypes.c_size_t()
    rc = lib.r6_glsl_pack_ubo(short, 4, alpha_regions, alpha_packed,
                              len(alpha_regions), ctypes.byref(written))
    if rc != R6_ERR_BUFFER or written.value != 8:
        failures.append("glsl ubo buffer: rc=%d size=%d" %
                        (rc, written.value))

    bad = (GlslRegion * 1)(GlslRegion(offset=0, size=8, kind=0, type=0))
    value = (GlslValue * 1)(GlslValue(f=1.0))
    output = ctypes.create_string_buffer(8)
    written = ctypes.c_size_t()
    rc = lib.r6_glsl_pack_ubo(output, 8, bad, value, 1,
                              ctypes.byref(written))
    if rc != R6_ERR_ARG:
        failures.append("glsl ubo invalid region: rc=%d" % rc)
    print("  glsl std140 pack: scalar, uint, vec4, mat4, buffer checks")


def test_corpus(dll, dump, failures):
    """Load every data script through the C host, as lua_probe does in Python."""
    bootstrap = os.path.join(dump, "data", "car", "tire", "script",
                             "TireDefine.lua")
    paths = []
    for base, _dirs, files in os.walk(os.path.join(dump, "data")):
        for name in files:
            if name.lower().endswith(".lua"):
                paths.append(os.path.join(base, name))
    paths.sort()
    if os.path.exists(bootstrap):
        paths = [p for p in paths if os.path.normcase(p) !=
                 os.path.normcase(bootstrap)]
        paths.insert(0, bootstrap)

    engine = Engine(dll, dump)
    bad = []
    try:
        engine.setting_const()
        for path in paths:
            try:
                engine.load(path)
            except RuntimeError as exc:
                bad.append("%s: %s" % (os.path.basename(path), exc))
        known = ["GetTirePos", "GetCenterPos", "GetCustomGTWingPos",
                 "GetStroboAeroListNumber", "ColorMax"]
        missing = [n for n in known if not engine.has(n)]
    finally:
        engine.close()
    print("  corpus: %d scripts, %d load errors, %d known globals missing"
          % (len(paths), len(bad), len(missing)))
    for line in bad[:10]:
        failures.append("corpus: " + line)
    for name in missing:
        failures.append("corpus: global %s missing after full load" % name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.environ.get("WMMT6_DUMP",
                                                     r"D:\Games\W6W-05"))
    ap.add_argument("--dll", default=os.path.join(ROOT, "build", "engine",
                                                  "r6_engine.dll"))
    ap.add_argument("--limit", type=int, default=40,
                    help="max .tex/.mdl files sampled")
    ap.add_argument("--skip-lua", action="store_true")
    ap.add_argument("--skip-assets", action="store_true")
    ap.add_argument("--corpus", action="store_true",
                    help="also load every data script through the C host")
    ap.add_argument("--skip-gzip", action="store_true")
    args = ap.parse_args()

    failures = []
    if not args.skip_lua:
        print("lua host")
        test_lua(args.dll, args.dump, failures)
    if args.corpus:
        print("script corpus")
        test_corpus(args.dll, args.dump, failures)
    if not args.skip_gzip:
        print("gzip")
        test_gzip(args.dll, args.dump, failures)
    if not args.skip_assets:
        print("assets")
        test_assets(args.dll, args.dump, failures, args.limit)
        test_nut_decode(args.dll, args.dump, failures)
        test_glsl_ubo(args.dll, args.dump, failures)
    if failures:
        print("\nFAILURES (%d)" % len(failures))
        for line in failures:
            print("  " + line)
        return 1
    print("\nall engine checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
