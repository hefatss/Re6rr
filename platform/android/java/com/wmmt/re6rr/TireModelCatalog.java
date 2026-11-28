package com.wmmt.re6rr;

/** Copied TireInfo paths, model names, enum tokens and wheel defaults. */
public final class TireModelCatalog {
    private TireModelCatalog() {
    }

    /** version, counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size, lines, span base, default span and color. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** string span for one of 16 slots in a file. */
    public static long[] span(byte[] blob, int index) {
        return nativeSpan(blob, index);
    }

    /** copied token, or empty string for a placeholder slot. */
    public static String text(byte[] blob, int index) {
        return nativeText(blob, index);
    }

    /** copied wheel_default string. */
    public static String wheelDefault(byte[] blob, int index) {
        return nativeDefault(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeSpan(byte[] blob, int index);

    private static native String nativeText(byte[] blob, int index);

    private static native String nativeDefault(byte[] blob, int index);
}
