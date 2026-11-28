package com.wmmt.re6rr;

/** Copied mini-sticker color row positions and verbatim numeric tokens. */
public final class MiniStickerColorCatalog {
    private MiniStickerColorCatalog() {
    }

    /** version, counts, source facts and reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size and row base. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied basename, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** source line, bank slot and three token offsets. */
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
