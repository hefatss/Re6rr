package com.wmmt.re6rr;

/** Copied side-sticker and vinyl color rows and numeric tokens. */
public final class StickerColorCatalog {
    private StickerColorCatalog() {
    }

    /** version, counts, source facts and reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, corpus kind, source size and row base. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied basename, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** source line, selector id and three token offsets. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied numeric token; slot 0..2, or null for a bad index. */
    public static String token(byte[] blob, int index, int slot) {
        return nativeToken(blob, index, slot);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeToken(byte[] blob, int index, int slot);
}
