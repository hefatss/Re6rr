package com.wmmt.re6rr;

/** Path and layout facts from stage-effect PCV float-triple tables. */
public final class PcvInventoryCatalog {
    private PcvInventoryCatalog() {
    }

    /** version, file count, string bytes, total bytes and triple count. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied path span, byte/triple counts and stride. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative .bin path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);
}
