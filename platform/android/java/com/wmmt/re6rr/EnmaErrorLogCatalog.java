package com.wmmt.re6rr;

/** Layout facts from shipped Enma ytErrorLogMerge text tables. */
public final class EnmaErrorLogCatalog {
    private EnmaErrorLogCatalog() {
    }

    /** version, file/line counts, total bytes and sector/vector splits. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied path span, byte/line counts, shape, line-length range, CRLF
     * count and distinct kind/tag count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative .txt path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);
}
