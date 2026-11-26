package com.wmmt.re6rr;

/** Shipped CGameInput getter probes and default config image as copied data. */
public final class EnmaSimFacts {
    private EnmaSimFacts() {
    }

    /** version, getter count, hit count, config size, strings size and
     * strings offset. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** getter name, export name and baseline (two values plus two strings). */
    public static long[] getter(byte[] blob, int index) {
        return nativeGetter(blob, index);
    }

    public static String getterName(byte[] blob, int index) {
        return nativeGetterName(blob, index);
    }

    public static String getterExport(byte[] blob, int index) {
        return nativeGetterExport(blob, index);
    }

    /** probe offset and raw value bits. */
    public static long[] hit(byte[] blob, int index) {
        return nativeHit(blob, index);
    }

    /** Copies the 4096-byte default config image. */
    public static byte[] config(byte[] blob) {
        return nativeConfig(blob);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeGetter(byte[] blob, int index);

    private static native String nativeGetterName(byte[] blob, int index);

    private static native String nativeGetterExport(byte[] blob, int index);

    private static native long[] nativeHit(byte[] blob, int index);

    private static native byte[] nativeConfig(byte[] blob);
}
