package com.wmmt.re6rr;

/** Shipped Enma DLL export names, copied from a derived blob. */
public final class EnmaExports {
    private EnmaExports() {
    }

    /** export count, strings offset and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Export name at an ordinal, or null for an invalid index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** Ordinal of an exact mangled name, or -1 when absent. */
    public static int find(byte[] blob, String name) {
        return nativeFind(blob, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String name);
}
