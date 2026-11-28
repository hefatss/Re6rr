package com.wmmt.re6rr;

/** Copied WANGAN hide-clip paths, tables, timestamps and model names. */
public final class HideClipModelTables {
    private HideClipModelTables() {
    }

    /** version, counts, string bytes and source totals. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/table/timestamp spans, source size, line and name counts. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied HIDE_MODEL_NN table name, or null for a bad index. */
    public static String table(byte[] blob, int index) {
        return nativeTable(blob, index);
    }

    /** copied source timestamp, or null for a bad index. */
    public static String timestamp(byte[] blob, int index) {
        return nativeTimestamp(blob, index);
    }

    /** copied ASCII model name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeTable(byte[] blob, int index);

    private static native String nativeTimestamp(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);
}
