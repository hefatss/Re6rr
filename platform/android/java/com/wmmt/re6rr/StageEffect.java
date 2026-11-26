package com.wmmt.re6rr;

/** Read the shipped stage-effect symbolic sound catalog. */
public final class StageEffect {
    private StageEffect() {
    }

    /** version, count, strings offset, strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** set, symbol, file, tone name, wav for one row. */
    public static String[] strings(byte[] blob, int index) {
        return nativeStrings(blob, index);
    }

    /** bank, tone, native tone, loop, x, y, z for one row. */
    public static double[] numbers(byte[] blob, int index) {
        return nativeNumbers(blob, index);
    }

    /** Row index for a symbol, or -1. */
    public static int find(byte[] blob, String symbol) {
        return nativeFind(blob, symbol);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String[] nativeStrings(byte[] blob, int index);

    private static native double[] nativeNumbers(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String symbol);
}
