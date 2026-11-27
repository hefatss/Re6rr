package com.wmmt.re6rr;

/** Fixed-stride layout facts from default ghost record tables. */
public final class DefaultGhostCatalog {
    private DefaultGhostCatalog() {
    }

    /** version, file/row counts, string bytes and copied layout offsets. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied path span, byte/record counts, code, name ranges and tuple counts. */
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
