package com.wmmt.re6rr;

/** Copied vinyl selector ids, row lines and numeric value tokens. */
public final class VinylSelectCatalog {
    private VinylSelectCatalog() {
    }

    /** version, counts, source facts, id range and reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size and row base. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied basename, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** source line, selector id and value offset. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied numeric value token, or null for a bad index. */
    public static String value(byte[] blob, int index) {
        return nativeValue(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeValue(byte[] blob, int index);
}
