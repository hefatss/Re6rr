package com.wmmt.re6rr;

/** Copied DISTCLIP paths, table names, key names and integer values. */
public final class DistClipCatalog {
    private DistClipCatalog() {
    }

    /** version, file/row counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/table spans, source size, line count, row base and row count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied global table name, or null for a bad index. */
    public static String table(byte[] blob, int index) {
        return nativeTable(blob, index);
    }

    /** copied row key, or null for a bad index. */
    public static String rowKey(byte[] blob, int index) {
        return nativeRowKey(blob, index);
    }

    /** copied row value, or -1 for a bad index. */
    public static int rowValue(byte[] blob, int index) {
        return nativeRowValue(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeTable(byte[] blob, int index);

    private static native String nativeRowKey(byte[] blob, int index);

    private static native int nativeRowValue(byte[] blob, int index);
}
