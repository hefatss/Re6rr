package com.wmmt.re6rr;

/** Copied rows from the shipped Zenichi name-plate configuration. */
public final class ZenichiConfigCatalog {
    private ZenichiConfigCatalog() {
    }

    /** version, row count, string bytes and source Lua byte size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** item id, variation, copied name span and layout. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** first row with the given item id, or null when absent. */
    public static long[] findId(byte[] blob, int item) {
        return nativeFindId(blob, item);
    }

    /** copied texture name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native long[] nativeFindId(byte[] blob, int item);

    private static native String nativeName(byte[] blob, int index);
}
