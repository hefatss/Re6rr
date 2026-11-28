package com.wmmt.re6rr;

/** Copied custom-frame IDs, texture names and accessor names. */
public final class CustomFrameCatalog {
    private CustomFrameCatalog() {
    }

    /** version, row/name/function counts, string bytes and source byte size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** id and four copied texture-name spans. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied texture name for slot 0..3, or null for a bad index. */
    public static String texture(byte[] blob, int index, int slot) {
        return nativeTexture(blob, index, slot);
    }

    /** copied Lua accessor name, or null for a bad index. */
    public static String function(byte[] blob, int index) {
        return nativeFunction(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeTexture(byte[] blob, int index,
                                               int slot);

    private static native String nativeFunction(byte[] blob, int index);
}
