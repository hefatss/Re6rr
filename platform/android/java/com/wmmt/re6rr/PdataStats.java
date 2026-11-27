package com.wmmt.re6rr;

/** Shipped .pdata size buckets and largest functions as copied facts. */
public final class PdataStats {
    private PdataStats() {
    }

    /** version, function count, code/text bytes, leaf/chained/EH counts,
     * min/max/median sizes, bucket/largest counts, strings size and offset. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** size-bucket label and row count. */
    public static long bucket(byte[] blob, int index) {
        return nativeBucket(blob, index);
    }

    public static String bucketLabel(byte[] blob, int index) {
        return nativeBucketLabel(blob, index);
    }

    /** begin, end, size, unwind RVA, flags, leaf, chain begin/end/unwind. */
    public static long[] largest(byte[] blob, int index) {
        return nativeLargest(blob, index);
    }

    public static String largestSection(byte[] blob, int index) {
        return nativeLargestSection(blob, index);
    }

    /** largest-row index for an exact begin RVA; -1 if absent. */
    public static long find(byte[] blob, long begin) {
        if (begin < 0 || begin > 0xFFFFFFFFL) {
            return -1;
        }
        return nativeFind(blob, begin);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long nativeBucket(byte[] blob, int index);

    private static native String nativeBucketLabel(byte[] blob, int index);

    private static native long[] nativeLargest(byte[] blob, int index);

    private static native String nativeLargestSection(byte[] blob, int index);

    private static native long nativeFind(byte[] blob, long begin);
}
