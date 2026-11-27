package com.wmmt.re6rr;

/** Shipped stage-effect gzip headers and inflated 16-byte prefixes. */
public final class GzEffectCatalog {
    private GzEffectCatalog() {
    }

    /** version, file count, string bytes, flag-0/flag-8 counts and
     * known/other prefix counts. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path offset/length, compressed size, gzip flags, mtime, xfl, OS,
     * ISIZE, inflated size, gzip header size and prefix length. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** dump-relative path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** exactly 16 inflated bytes, zero-padded when the stream is shorter. */
    public static byte[] prefix(byte[] blob, int index) {
        return nativePrefix(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native byte[] nativePrefix(byte[] blob, int index);
}
