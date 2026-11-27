package com.wmmt.re6rr;

/** Shipped x64 reference-word xrefs as copied counts and RVAs. */
public final class RefWords {
    private RefWords() {
    }

    /** version, word count and xref count. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** raw word value, first xref index and xref count. */
    public static long[] word(byte[] blob, int index) {
        return nativeWord(blob, index);
    }

    public static long xref(byte[] blob, int index) {
        return nativeXref(blob, index);
    }

    public static long wordXref(byte[] blob, int wordIndex, int localIndex) {
        return nativeWordXref(blob, wordIndex, localIndex);
    }

    /** word index for an exact raw value; -1 if absent. */
    public static long find(byte[] blob, long value) {
        if (value < 0 || value > 0xFFFFFFFFL) {
            return -1;
        }
        return nativeFind(blob, value);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeWord(byte[] blob, int index);

    private static native long nativeXref(byte[] blob, int index);

    private static native long nativeWordXref(byte[] blob, int wordIndex,
                                              int localIndex);

    private static native long nativeFind(byte[] blob, long value);
}
