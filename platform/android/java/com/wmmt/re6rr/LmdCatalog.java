package com.wmmt.re6rr;

/** Gzip/XMD.001 header facts from the shipped .LMD flash files. */
public final class LmdCatalog {
    private LmdCatalog() {
    }

    /** version, file count, streams per file and path-string bytes. */
    public static int[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** compressed size, gzip flags, mtime, xfl/os, ISIZE, inflated size,
     * XMD version and first stream index. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** relative path inside the dump, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        byte[] raw = nativePath(blob, index);
        return raw == null ? null : new String(raw,
                java.nio.charset.StandardCharsets.US_ASCII);
    }

    /** XMD stream offset and derived size, or null for a bad index. */
    public static long[] stream(byte[] blob, int index, int local) {
        return nativeStream(blob, index, local);
    }

    private static native int[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native byte[] nativePath(byte[] blob, int index);

    private static native long[] nativeStream(byte[] blob, int index,
                                              int local);
}
