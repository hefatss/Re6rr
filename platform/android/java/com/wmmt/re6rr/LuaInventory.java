package com.wmmt.re6rr;

/** Shipped Lua file counts, per-directory logic statistics and name lists. */
public final class LuaInventory {
    public static final int DEFINED_NAMES = 0;
    public static final int NATIVE_TOP = 1;
    public static final int UNDEFINED_TOP = 2;

    private LuaInventory() {
    }

    /** root count, dir count, strings size, six counts for each root, then
     *  six count/offset pairs for each root's defined/native/undefined tables. */
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

    /** {name, decimal count}; count is "0" for defined names. Null if invalid. */
    public static String[] symbol(byte[] blob, int root, int kind, int index) {
        return nativeSymbol(blob, root, kind, index);
    }

    /** {index, count} for the first exact name, or null when absent. */
    public static long[] findSymbol(byte[] blob, int root, int kind,
                                    String name) {
        return nativeFindSymbol(blob, root, kind, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, int root, String name);

    private static native String[] nativeSymbol(byte[] blob, int root,
                                                int kind, int index);

    private static native long[] nativeFindSymbol(byte[] blob, int root,
                                                  int kind, String name);
}
