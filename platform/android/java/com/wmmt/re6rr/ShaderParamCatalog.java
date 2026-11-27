package com.wmmt.re6rr;

/** Numeric parameters from shipped per-car shader Lua files. */
public final class ShaderParamCatalog {
    private ShaderParamCatalog() {
    }

    /** version, file count, string bytes and two reserved fields. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path offset/length and model offset/length for one file. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** eight copied float32 values in day/night environment order. */
    public static double[] values(byte[] blob, int index) {
        return nativeValues(blob, index);
    }

    /** copied dump-relative Lua path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied model name derived from the Lua filename. */
    public static String model(byte[] blob, int index) {
        return nativeModel(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native double[] nativeValues(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeModel(byte[] blob, int index);
}
