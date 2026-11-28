package com.wmmt.re6rr;

/** Copied PLC_MA61_Specification.lua key and ASCII literal rows. */
public final class SpecMa61Catalog {
    private SpecMa61Catalog() {
    }

    /** version, counts, source facts, table span and path span. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied source path, or null for a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** key/literal spans, kind, line and comment flag. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied key name, or null for a bad index. */
    public static String key(byte[] blob, int index) {
        return nativeKey(blob, index);
    }

    /** copied ASCII literal; empty for non-ASCII literals. */
    public static String literal(byte[] blob, int index) {
        return nativeLiteral(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeKey(byte[] blob, int index);

    private static native String nativeLiteral(byte[] blob, int index);
}
