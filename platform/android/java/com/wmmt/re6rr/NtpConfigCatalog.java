package com.wmmt.re6rr;

/** Copied NTP config paths and verbatim ASCII lines. */
public final class NtpConfigCatalog {
    private NtpConfigCatalog() {
    }

    /** version, counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size, line count and line base. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** text span and kind: 0 blank, 1 comment, 2 active. */
    public static long[] line(byte[] blob, int index) {
        return nativeLine(blob, index);
    }

    /** copied line text, empty for a blank line. */
    public static String text(byte[] blob, int index) {
        return nativeText(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeLine(byte[] blob, int index);

    private static native String nativeText(byte[] blob, int index);
}
