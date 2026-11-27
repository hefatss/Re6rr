package com.wmmt.re6rr;

/** Validated 0x100 headers from the shipped .MED motion files. */
public final class MedHeaders {
    private MedHeaders() {
    }

    /** version, row count, header offset (0x100) and path-string bytes. */
    public static int[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** file size, frame count and the eight raw header words in order. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** relative path inside the dump, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        byte[] raw = nativePath(blob, index);
        return raw == null ? null : new String(raw,
                java.nio.charset.StandardCharsets.US_ASCII);
    }

    private static native int[] nativeHeader(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native byte[] nativePath(byte[] blob, int index);
}
