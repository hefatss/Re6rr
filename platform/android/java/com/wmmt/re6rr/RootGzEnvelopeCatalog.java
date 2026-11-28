package com.wmmt.re6rr;

/** Copied root gzip envelope words; inflated payloads stay in native code. */
public final class RootGzEnvelopeCatalog {
    private RootGzEnvelopeCatalog() {
    }

    /** version, counts, source bytes and string size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** name span, compressed size, gzip words and validity flag. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied basename, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);
}
