package com.wmmt.re6rr;

/** Structured SM4 control-flow map for the 446 shipped NSXR records. */
public final class ShaderControlFlow {
    public static final int IF = 0;
    public static final int LOOP = 1;
    public static final int SWITCH = 2;
    public static final int CASE = 0;
    public static final int DEFAULT = 1;
    public static final int VERTEX = 0;
    public static final int PIXEL = 1;

    private ShaderControlFlow() {
    }

    /** version, record/block/case/index counts and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** name offset, stage, first block/block count, unmatched first/count. */
    public static long[] record(byte[] blob, int index) {
        return nativeRecord(blob, index);
    }

    /** Shipped shader file name for one record, or null on bad input. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** First record for an exact shader name and stage, or -1 when absent. */
    public static int find(byte[] blob, String name, int stage) {
        return nativeFind(blob, name, stage);
    }

    /** kind, start, end, else, case/index first and count values for a block. */
    public static long[] block(byte[] blob, int index) {
        return nativeBlock(blob, index);
    }

    /** kind and instruction index for one CASE/DEFAULT row. */
    public static long[] caseAt(byte[] blob, int index) {
        return nativeCase(blob, index);
    }

    /** One break, continue or unmatched instruction index, or -1 if invalid. */
    public static long indexAt(byte[] blob, int index) {
        return nativeIndex(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRecord(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String name, int stage);

    private static native long[] nativeBlock(byte[] blob, int index);

    private static native long[] nativeCase(byte[] blob, int index);

    private static native long nativeIndex(byte[] blob, int index);
}
