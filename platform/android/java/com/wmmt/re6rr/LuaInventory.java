package com.wmmt.re6rr;

/** Shipped Lua file counts and per-directory logic statistics. */
public final class LuaInventory {
    private LuaInventory() {
    }

    /** root count, dir count, strings size, then six counts for each root. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Directory name at an ordinal, or null for an invalid index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** root, files, bytes and logic-file count, or null for invalid index. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** Ordinal of one directory inside a root, or -1 when absent. */
    public static int find(byte[] blob, int root, String name) {
        return nativeFind(blob, root, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, int root, String name);
}
