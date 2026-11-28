package com.wmmt.re6rr;

/** Copied record layout facts from hints.dat. */
public final class HintsCatalog {
    private HintsCatalog() {
    }

    /** version, record count, stride, source byte size and distinct count. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** four copied opaque u32 words from one 16-byte record. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);
}
