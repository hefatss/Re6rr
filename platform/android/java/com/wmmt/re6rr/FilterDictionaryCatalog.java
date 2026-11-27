package com.wmmt.re6rr;

/** Structural line shapes from shipped filter dictionary Lua files. */
public final class FilterDictionaryCatalog {
    private FilterDictionaryCatalog() {
    }

    /** version, file count, row count, string bytes, source bytes/lines. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied source size, line count, kind counts and row range. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative Lua path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** file index, line index, byte offset, length, kind and value. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);
}
