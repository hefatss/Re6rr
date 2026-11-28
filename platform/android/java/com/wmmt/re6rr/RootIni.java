package com.wmmt.re6rr;

/** Copied root INI sections, keys, values and comments. */
public final class RootIni {
    private RootIni() {
    }

    /** version, counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/section spans, source size, line/key/comment counts. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied [Section] name, or null for a bad index. */
    public static String section(byte[] blob, int index) {
        return nativeSection(blob, index);
    }

    /** copied key name, or null for a bad index. */
    public static String key(byte[] blob, int index) {
        return nativeKey(blob, index);
    }

    /** copied value text, or null for a bad index. */
    public static String value(byte[] blob, int index) {
        return nativeValue(blob, index);
    }

    /** copied ; comment line, or null for a bad index. */
    public static String comment(byte[] blob, int index) {
        return nativeComment(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeSection(byte[] blob, int index);

    private static native String nativeKey(byte[] blob, int index);

    private static native String nativeValue(byte[] blob, int index);

    private static native String nativeComment(byte[] blob, int index);
}
