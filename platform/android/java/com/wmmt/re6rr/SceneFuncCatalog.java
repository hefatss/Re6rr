package com.wmmt.re6rr;

/** Copied scene function names and return expressions. */
public final class SceneFuncCatalog {
    private SceneFuncCatalog() {
    }

    /** version, file/function counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source size, lines, function base and count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** name/result spans for one definition. */
    public static long[] func(byte[] blob, int index) {
        return nativeFunc(blob, index);
    }

    /** copied function name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied return expression, or null for a bad index. */
    public static String result(byte[] blob, int index) {
        return nativeResult(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeFunc(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeResult(byte[] blob, int index);
}
