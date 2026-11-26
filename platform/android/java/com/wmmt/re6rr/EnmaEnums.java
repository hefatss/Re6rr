package com.wmmt.re6rr;

/** 16 exported Enma enum domains with shipped symbol names. */
public final class EnmaEnums {
    private EnmaEnums() {
    }

    /** enum count, strings offset and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Enum type name, or null for an invalid index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** Number of values, or -1 for an invalid index. */
    public static int count(byte[] blob, int index) {
        return nativeCount(blob, index);
    }

    /** Integer value at an ordinal, or -1 for invalid index/ordinal. */
    public static long value(byte[] blob, int index, int ordinal) {
        return nativeValue(blob, index, ordinal);
    }

    /** Symbol at an ordinal, or null for invalid index/ordinal. */
    public static String symbol(byte[] blob, int index, int ordinal) {
        return nativeSymbol(blob, index, ordinal);
    }

    /** Symbol for an integer value, or null when absent. */
    public static String find(byte[] blob, int index, long value) {
        return nativeFind(blob, index, value);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native int nativeCount(byte[] blob, int index);

    private static native long nativeValue(byte[] blob, int index, int ordinal);

    private static native String nativeSymbol(byte[] blob, int index, int ordinal);

    private static native String nativeFind(byte[] blob, int index, long value);
}
