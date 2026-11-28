package com.wmmt.re6rr;

/** Copied story-rival block names, line spans and keyword rows. */
public final class RivalBlockCatalog {
    private RivalBlockCatalog() {
    }

    /** version, counts, source bytes and line total. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied source path, or null for a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** name span, line span, five row spans and five counts. */
    public static long[] block(byte[] blob, int index) {
        return nativeBlock(blob, index);
    }

    /** copied ECharacter_* block name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied keyword row, or null for a bad index/keyword. */
    public static String keyword(byte[] blob, int index, int keyword) {
        return nativeKeyword(blob, index, keyword);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeBlock(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeKeyword(byte[] blob, int index,
                                               int keyword);
}
