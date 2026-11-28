package com.wmmt.re6rr;

/** Copied charCar default color block names, positions and numeric tokens. */
public final class CharColorCatalog {
    private CharColorCatalog() {
    }

    /** version, counts, source facts and COLOR_MAX distribution. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, size, lines, COLOR_MAX, list line, row base and block size. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied block name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** name span, source line and token base offset. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied numeric token; slot 0..18, or null for a bad index. */
    public static String token(byte[] blob, int index, int slot) {
        return nativeToken(blob, index, slot);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeToken(byte[] blob, int index, int slot);
}
