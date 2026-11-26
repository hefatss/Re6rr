package com.wmmt.re6rr;

/** Shipped Lua globals that wmn6r.exe looks up and calls. */
public final class LuaGlobals {
    private LuaGlobals() {
    }

    /** count, strings offset and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Global name, or null for an invalid index or blob. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** call count and category index, or null for an invalid index. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);
}
