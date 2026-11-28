package com.wmmt.re6rr;

/** Copied story-series block headers and token lines. */
public final class StorySeriesTokens {
    private StorySeriesTokens() {
    }

    /** version, block/line counts, string bytes and source sizes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** header span and line count for one block. */
    public static long[] block(byte[] blob, int index) {
        return nativeBlock(blob, index);
    }

    /** copied ESeries_* header line, or null for a bad index. */
    public static String headerToken(byte[] blob, int index) {
        return nativeHeaderToken(blob, index);
    }

    /** copied token line before // comments, or null for a bad index. */
    public static String line(byte[] blob, int index) {
        return nativeLine(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeBlock(byte[] blob, int index);

    private static native String nativeHeaderToken(byte[] blob, int index);

    private static native String nativeLine(byte[] blob, int index);
}
