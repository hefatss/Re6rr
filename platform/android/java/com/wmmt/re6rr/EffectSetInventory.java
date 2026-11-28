package com.wmmt.re6rr;

/** Copied stage-effect SET_*.lua paths, names and row strings. */
public final class EffectSetInventory {
    private EffectSetInventory() {
    }

    /** version, file/row counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/name/num spans, source size, row count and row base. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied set name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied num integer token, or null for a bad index. */
    public static String num(byte[] blob, int index) {
        return nativeNum(blob, index);
    }

    /** copied row path string, or null for a bad index. */
    public static String rowPath(byte[] blob, int index) {
        return nativeRowPath(blob, index);
    }

    /** copied row model string, or null for a bad index. */
    public static String rowModel(byte[] blob, int index) {
        return nativeRowModel(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeNum(byte[] blob, int index);

    private static native String nativeRowPath(byte[] blob, int index);

    private static native String nativeRowModel(byte[] blob, int index);
}
