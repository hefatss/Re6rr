"""Small Lua 5.1 host for the script-driven part of wmn6r.exe.

    from lua_host import LuaHost

The 219 names in docs/recon/BINDINGS.md are *not* lua_CFunctions. Ghidra shows
`FUN_1400ffb60` and friends doing `lua_getfield(L, LUA_GLOBALSINDEX, name)`,
pushing one or two arguments, `lua_pcall(L, n, LUA_MULTRET, 0)` and reading the
top three results as a Vec3 (`FUN_1400d20d0`). The implementations are Lua
functions defined by the game's data scripts. The port therefore needs a Lua
5.1 VM that loads those scripts and lets native code call their globals.

This module is a validation host: it uses the dump's own lua5.1.dll through
ctypes. The Android engine will link Lua 5.1 and follow the same call protocol.
"""

import ctypes
import gzip
import os

LUA_GLOBALSINDEX = -10002
LUA_MULTRET = -1
LUA_TNIL = 0
LUA_TBOOLEAN = 1
LUA_TNUMBER = 3
LUA_TSTRING = 4
LUA_TTABLE = 5
LUA_TFUNCTION = 6


class LuaError(RuntimeError):
    """A script failed to load or a Lua call raised an error."""


class LuaHost:
    """Wrap the Lua 5.1 C API with a few Python-friendly helpers."""

    def __init__(self, lua_path=None):
        self.lua_path = lua_path or os.environ.get("LUA51_DLL", "lua5.1.dll")
        self.lib = ctypes.CDLL(self.lua_path)
        self._callbacks = []
        self._missing = {}
        self._track_missing = False
        self._bind_api()
        self.L = self.lib.luaL_newstate()
        if not self.L:
            raise LuaError("luaL_newstate failed")
        self.lib.luaL_openlibs(self.L)

    def _bind_api(self):
        lib = self.lib
        lib.luaL_newstate.restype = ctypes.c_void_p
        lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
        lib.luaL_loadbuffer.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                        ctypes.c_size_t, ctypes.c_char_p]
        lib.luaL_loadbuffer.restype = ctypes.c_int
        lib.lua_close.argtypes = [ctypes.c_void_p]
        lib.lua_gettop.argtypes = [ctypes.c_void_p]
        lib.lua_gettop.restype = ctypes.c_int
        lib.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int]
        lib.lua_pcall.restype = ctypes.c_int
        lib.lua_getfield.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                     ctypes.c_char_p]
        lib.lua_setfield.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                     ctypes.c_char_p]
        lib.lua_pushnil.argtypes = [ctypes.c_void_p]
        lib.lua_pushnumber.argtypes = [ctypes.c_void_p, ctypes.c_double]
        lib.lua_pushinteger.argtypes = [ctypes.c_void_p, ctypes.c_longlong]
        lib.lua_pushlstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                        ctypes.c_size_t]
        lib.lua_pushboolean.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.lua_pushcclosure.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_int]
        lib.lua_createtable.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                        ctypes.c_int]
        lib.lua_type.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.lua_type.restype = ctypes.c_int
        lib.lua_tonumber.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.lua_tonumber.restype = ctypes.c_double
        lib.lua_toboolean.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.lua_toboolean.restype = ctypes.c_int
        lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                      ctypes.POINTER(ctypes.c_size_t)]
        lib.lua_tolstring.restype = ctypes.c_char_p
        lib.lua_setmetatable.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)

    def close(self):
        if self.L:
            self.lib.lua_close(self.L)
            self.L = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _error(self):
        p = self.lib.lua_tolstring(self.L, -1, None)
        msg = p.decode("cp932", "replace") if p else "unknown Lua error"
        self.lib.lua_settop(self.L, -2)
        return LuaError(msg)

    def _check(self, rc):
        if rc:
            raise self._error()
        return rc

    @staticmethod
    def _decode(raw, name):
        if raw[:3] == b"\x1f\x8b\x08":
            raw = gzip.decompress(raw)
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        return raw

    def load_bytes(self, raw, name):
        """Load and run one script chunk."""
        raw = self._decode(raw, name)
        label = os.path.basename(name).encode("ascii", "replace")
        rc = self.lib.luaL_loadbuffer(self.L, raw, len(raw), label)
        if rc == 0:
            rc = self.lib.lua_pcall(self.L, 0, 0, 0)
        self._check(rc)
        self.lib.lua_settop(self.L, 0)

    def load_file(self, path):
        with open(path, "rb") as f:
            self.load_bytes(f.read(), path)

    def _push(self, value):
        if value is None:
            self.lib.lua_pushnil(self.L)
        elif isinstance(value, bool):
            self.lib.lua_pushboolean(self.L, int(value))
        elif isinstance(value, int):
            self.lib.lua_pushinteger(self.L, value)
        elif isinstance(value, float):
            self.lib.lua_pushnumber(self.L, value)
        elif isinstance(value, bytes):
            self.lib.lua_pushlstring(self.L, value, len(value))
        elif isinstance(value, str):
            b = value.encode("cp932", "replace")
            self.lib.lua_pushlstring(self.L, b, len(b))
        else:
            raise TypeError("cannot push %r to Lua" % (value,))

    def set_number(self, name, value):
        self._push(value)
        self.lib.lua_setfield(self.L, LUA_GLOBALSINDEX, name.encode("ascii"))

    def set_table(self, name, fields):
        """Set a global table; nested dicts become nested tables."""
        self.lib.lua_createtable(self.L, 0, len(fields))
        for key, value in fields.items():
            if isinstance(value, dict):
                self.set_table(None, value)
            else:
                self._push(value)
            self.lib.lua_setfield(self.L, -2, key.encode("ascii"))
        if name is None:
            return  # leave the nested table on the stack for the caller
        self.lib.lua_setfield(self.L, LUA_GLOBALSINDEX, name.encode("ascii"))

    def set_function(self, name, fn):
        """Expose a Python callable as a global function returning one value."""
        def callback(L):
            n = self.lib.lua_gettop(L)
            args = [self._read(i) for i in range(1, n + 1)]
            try:
                self._push(fn(*args))
            except Exception:
                self.lib.lua_pushnil(L)
            return 1
        cb = self._callback_type(callback)
        self._callbacks.append(cb)
        self.lib.lua_pushcclosure(self.L, ctypes.cast(cb, ctypes.c_void_p), 0)
        self.lib.lua_setfield(self.L, LUA_GLOBALSINDEX, name.encode("ascii"))

    def _read(self, idx):
        kind = self.lib.lua_type(self.L, idx)
        if kind == LUA_TNIL:
            return None
        if kind == LUA_TBOOLEAN:
            return bool(self.lib.lua_toboolean(self.L, idx))
        if kind == LUA_TNUMBER:
            return self.lib.lua_tonumber(self.L, idx)
        if kind == LUA_TSTRING:
            size = ctypes.c_size_t()
            p = self.lib.lua_tolstring(self.L, idx, ctypes.byref(size))
            return ctypes.string_at(p, size.value).decode("cp932", "replace")
        if kind == LUA_TTABLE:
            return "<table>"
        if kind == LUA_TFUNCTION:
            return "<function>"
        return "<%d>" % kind

    def global_type(self, name):
        self.lib.lua_getfield(self.L, LUA_GLOBALSINDEX, name.encode("ascii"))
        kind = self.lib.lua_type(self.L, -1)
        self.lib.lua_settop(self.L, -2)
        return kind

    def call(self, name, *args, **kwargs):
        """Call a Lua global, returning all results (like lua_pcall + MULTRET)."""
        nresults = kwargs.pop("nresults", None)
        if kwargs:
            raise TypeError("unexpected keyword %s" % next(iter(kwargs)))
        top = self.lib.lua_gettop(self.L)
        self.lib.lua_getfield(self.L, LUA_GLOBALSINDEX, name.encode("ascii"))
        if self.lib.lua_type(self.L, -1) != LUA_TFUNCTION:
            self.lib.lua_settop(self.L, top)
            raise LuaError("%s is not a function" % name)
        for arg in args:
            self._push(arg)
        wanted = LUA_MULTRET if nresults is None else nresults
        rc = self.lib.lua_pcall(self.L, len(args), wanted, 0)
        if rc:
            err = self._error()
            self.lib.lua_settop(self.L, top)
            raise err
        count = self.lib.lua_gettop(self.L) - top
        values = [self._read(top + 1 + i) for i in range(count)]
        self.lib.lua_settop(self.L, top)
        return values

    def call_vec3(self, name, *args):
        """Read the top three results as the engine's FUN_1400d20d0 does."""
        values = self.call(name, *args, nresults=3)
        if not all(isinstance(v, (int, float)) for v in values):
            raise LuaError("%s did not return three numbers: %r" % (name, values))
        return tuple(float(v) for v in values)

    def track_missing_globals(self):
        """Log reads of globals that no script or native stub defines."""
        def callback(L):
            size = ctypes.c_size_t()
            p = self.lib.lua_tolstring(L, 1, ctypes.byref(size))
            if p:
                key = ctypes.string_at(p, size.value).decode("cp932", "replace")
                self._missing[key] = self._missing.get(key, 0) + 1
            self.lib.lua_pushnil(L)
            return 1
        cb = self._callback_type(callback)
        self._callbacks.append(cb)
        self.lib.lua_pushcclosure(self.L, ctypes.cast(cb, ctypes.c_void_p), 0)
        self.lib.lua_setfield(self.L, LUA_GLOBALSINDEX, b"_LogMissingGlobal")
        prelude = (b'setmetatable(_G, {__index = function(t, k) '
                   b'return _LogMissingGlobal(tostring(k)) end})')
        self.load_bytes(prelude, "lua_host_prelude")
        self._track_missing = True
        self._missing.clear()

    @property
    def missing_globals(self):
        return dict(self._missing)
