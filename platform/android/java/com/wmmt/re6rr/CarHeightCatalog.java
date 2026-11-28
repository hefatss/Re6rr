package com.wmmt.re6rr;

/** Copied car height and aero row positions, labels and numeric tokens. */
public final class CarHeightCatalog {
    private CarHeightCatalog() {
    }

    /** version, counts, source facts and reserved word. */
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

    /** source line, token offsets and label span. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied numeric token; slot 0..1, or null for a bad index. */
    public static String token(byte[] blob, int index, int slot) {
        return nativeToken(blob, index, slot);
    }

    /** copied aero label, or null for a height row. */
    public static String label(byte[] blob, int index) {
        return nativeLabel(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeToken(byte[] blob, int index, int slot);

    private static native String nativeLabel(byte[] blob, int index);
}
