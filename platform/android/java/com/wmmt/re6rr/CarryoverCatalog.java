package com.wmmt.re6rr;

/** Copied ytCarryover.txt series token, scalars and row tokens. */
public final class CarryoverCatalog {
    private CarryoverCatalog() {
    }

    /** version, counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** text span, kind and source line; index 0 is the source path. */
    public static long[] record(byte[] blob, int index) {
        return nativeRecord(blob, index);
    }

    /** copied verbatim record token, or null for a bad index. */
    public static String text(byte[] blob, int index) {
        return nativeText(blob, index);
    }

    /** seven token spans and the source line. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** row field 0..6: bool, number, token and four floats. */
    public static String field(byte[] blob, int index, int field) {
        return nativeField(blob, index, field);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRecord(byte[] blob, int index);

    private static native String nativeText(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeField(byte[] blob, int index,
                                             int field);
}
