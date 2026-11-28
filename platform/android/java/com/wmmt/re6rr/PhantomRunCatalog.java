package com.wmmt.re6rr;

/** Copied header words and u64 rows from ytPhantomTempRun.bin. */
public final class PhantomRunCatalog {
    private PhantomRunCatalog() {
    }

    /** counts, source size and six copied header words. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied timestamp word, or -1 for a bad index. */
    public static long timestamp(byte[] blob, int index) {
        return nativeTimestamp(blob, index);
    }

    /** copied record word, or -1 for a bad index. */
    public static long record(byte[] blob, int index) {
        return nativeRecord(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long nativeTimestamp(byte[] blob, int index);

    private static native long nativeRecord(byte[] blob, int index);
}
