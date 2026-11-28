package com.wmmt.re6rr;

/** Copied NavimapParam.lua names and integer literals. */
public final class NavimapParam {
    private NavimapParam() {
    }

    /** version, spans, source totals and row counts. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** name/value spans and active flag for one scalar row. */
    public static long[] scalar(byte[] blob, int index) {
        return nativeScalar(blob, index);
    }

    /** copied source path, or null on a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** copied NAVIMAP_USE table name, or null on a bad blob. */
    public static String tableName(byte[] blob) {
        return nativeTableName(blob);
    }

    /** copied scalar name, or null for a bad index. */
    public static String scalarName(byte[] blob, int index) {
        return nativeScalarName(blob, index);
    }

    /** copied scalar integer literal, or null for a bad index. */
    public static String scalarValue(byte[] blob, int index) {
        return nativeScalarValue(blob, index);
    }

    /** copied table integer literal, or null for a bad index. */
    public static String tableValue(byte[] blob, int index) {
        return nativeTableValue(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeScalar(byte[] blob, int index);

    private static native String nativePath(byte[] blob);

    private static native String nativeTableName(byte[] blob);

    private static native String nativeScalarName(byte[] blob, int index);

    private static native String nativeScalarValue(byte[] blob, int index);

    private static native String nativeTableValue(byte[] blob, int index);
}
