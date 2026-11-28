package com.wmmt.re6rr;

/** Copied Strobo parameter integers, table names and accessor names. */
public final class StroboParameter {
    private StroboParameter() {
    }

    /** version, counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size, lines, debug code and row bases. */
    public static long[] file(byte[] blob) {
        return nativeFile(blob);
    }

    /** copied source path, or null for a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** name span, row base and row count. */
    public static long[] table(byte[] blob, int index) {
        return nativeTable(blob, index);
    }

    /** copied table name, or null for a bad index. */
    public static String tableName(byte[] blob, int index) {
        return nativeTableName(blob, index);
    }

    /** copied integer pair. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied accessor name, or null for a bad index. */
    public static String function(byte[] blob, int index) {
        return nativeFunction(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeTable(byte[] blob, int index);

    private static native String nativeTableName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeFunction(byte[] blob, int index);
}
