package com.wmmt.re6rr;

/** Copied AMCUS INI section and key names; raw values stay in native code. */
public final class AmcusIniKeysCatalog {
    private AmcusIniKeysCatalog() {
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

    /** name span, kind, line, value flag and section index. */
    public static long[] line(byte[] blob, int index) {
        return nativeLine(blob, index);
    }

    /** copied section/key name, empty for comment or blank lines. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeLine(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);
}
