package com.wmmt.re6rr;

/** Copied MA61 color block names and numeric tokens. */
public final class ColorBlockCatalog {
    private ColorBlockCatalog() {
    }

    /** version, counts, source facts and token shape. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size, line count, first row and row base. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** name span, source line and token base offset. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied block name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied numeric token; slot 0..18, or null for a bad index. */
    public static String token(byte[] blob, int index, int slot) {
        return nativeToken(blob, index, slot);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeToken(byte[] blob, int index, int slot);
}
