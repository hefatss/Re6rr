package com.wmmt.re6rr;

/** Raw RESOURCE:NU header prefixes from the shipped .ACT effect actors. */
public final class ActHeaders {
    private ActHeaders() {
    }

    /** version, row count, prefix size and path-string bytes. */
    public static int[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** shipped file size in bytes, or -1 for a bad index. */
    public static long size(byte[] blob, int index) {
        return nativeSize(blob, index);
    }

    /** relative path inside the dump, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        byte[] raw = nativePath(blob, index);
        return raw == null ? null : new String(raw,
                java.nio.charset.StandardCharsets.US_ASCII);
    }

    /** first 64 shipped bytes verbatim, or null for a bad index. */
    public static byte[] prefix(byte[] blob, int index) {
        return nativePrefix(blob, index);
    }

    private static native int[] nativeHeader(byte[] blob);

    private static native long nativeSize(byte[] blob, int index);

    private static native byte[] nativePath(byte[] blob, int index);

    private static native byte[] nativePrefix(byte[] blob, int index);
}
