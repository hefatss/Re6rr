package com.wmmt.re6rr;

/** Copied car vinyl blend list names, row positions and numeric tokens. */
public final class ColorVinylBlendCatalog {
    private ColorVinylBlendCatalog() {
    }

    /** version, counts, source facts and reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied source path, or null for a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** list name span, source line and token span/count. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied numeric token; slot 0..1, or null for a bad index. */
    public static String token(byte[] blob, int index, int slot) {
        return nativeToken(blob, index, slot);
    }

    /** accessor name span and source line. */
    public static long[] function(byte[] blob, int index) {
        return nativeFunction(blob, index);
    }

    /** copied accessor name, or null for a bad index. */
    public static String functionName(byte[] blob, int index) {
        return nativeFunctionName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeToken(byte[] blob, int index, int slot);

    private static native long[] nativeFunction(byte[] blob, int index);

    private static native String nativeFunctionName(byte[] blob, int index);
}
