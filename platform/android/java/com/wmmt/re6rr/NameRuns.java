package com.wmmt.re6rr;

/** Shipped plain string-pointer runs, names and code references. */
public final class NameRuns {
    private NameRuns() {
    }

    /** version, run count, name count, user count and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** rva, table size, stride, name count, first name, first user and user
     * count for one pointer run. */
    public static long[] run(byte[] blob, int index) {
        return nativeRun(blob, index);
    }

    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    public static String runName(byte[] blob, int runIndex, int localIndex) {
        return nativeRunName(blob, runIndex, localIndex);
    }

    public static long user(byte[] blob, int index) {
        return nativeUser(blob, index);
    }

    /** first code-reference row with an exact RVA; -1 if absent. */
    public static long findUser(byte[] blob, long rva) {
        if (rva < 0 || rva > 0xFFFFFFFFL) {
            return -1;
        }
        return nativeFindUser(blob, rva);
    }

    /** run, local and global indexes of the first exact match; null if none. */
    public static long[] find(byte[] blob, String name) {
        return nativeFind(blob, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRun(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeRunName(byte[] blob, int runIndex,
                                               int localIndex);

    private static native long nativeUser(byte[] blob, int index);

    private static native long[] nativeFind(byte[] blob, String name);

    private static native long nativeFindUser(byte[] blob, long rva);
}
