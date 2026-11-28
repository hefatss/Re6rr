package com.wmmt.re6rr;

/** Copied related-section paths, file sizes and integer row pairs. */
public final class RelatedSection {
    private RelatedSection() {
    }

    /** version, file/string/pair counts and two LOAD_SPEED integers. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, byte size, pair count and two LOAD_SPEED integers. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** twelve copied integers from one related-section row pair. */
    public static long[] pair(byte[] blob, int index) {
        return nativePair(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativePair(byte[] blob, int index);
}
