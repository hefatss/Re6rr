package com.wmmt.re6rr;

/** Copied tire, lamp and strobo section rows and numeric tokens. */
public final class TireLampPosCatalog {
    private TireLampPosCatalog() {
    }

    /** version, counts, source facts and reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path and car id spans, source facts and section span. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied basename, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied embedded car id, or null for a bad index. */
    public static String carId(byte[] blob, int index) {
        return nativeCarId(blob, index);
    }

    /** key span, source line, kind, value span and row span. */
    public static long[] section(byte[] blob, int index) {
        return nativeSection(blob, index);
    }

    /** copied section key, or null for a bad index. */
    public static String key(byte[] blob, int index) {
        return nativeKey(blob, index);
    }

    /** copied scalar count token, or null for a vector section. */
    public static String value(byte[] blob, int index) {
        return nativeValue(blob, index);
    }

    /** source line and three token offsets. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied numeric token; slot 0..2, or null for a bad index. */
    public static String token(byte[] blob, int index, int slot) {
        return nativeToken(blob, index, slot);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeCarId(byte[] blob, int index);

    private static native long[] nativeSection(byte[] blob, int index);

    private static native String nativeKey(byte[] blob, int index);

    private static native String nativeValue(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeToken(byte[] blob, int index, int slot);
}
