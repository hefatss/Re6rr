package com.wmmt.re6rr;

/** Fixed-stride layout facts from street-lamp tables. */
public final class StreetLampCatalog {
    private StreetLampCatalog() {
    }

    /** version, file count, string bytes, total bytes/records and stride. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied path span, byte/record counts, stride and u32 flag range. */
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
