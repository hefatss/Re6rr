package com.wmmt.re6rr;

/** Row counts and literal integer facts from ghost-region Lua tables. */
public final class GhostRegionCatalog {
    private GhostRegionCatalog() {
    }

    /** version, file count, string bytes, source bytes/lines and row totals. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied path span, source spans, row counts, region value range and the
     * three defeated-region integers. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative .lua path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);
}
