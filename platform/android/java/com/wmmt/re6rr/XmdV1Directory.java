package com.wmmt.re6rr;

/** Copied XMD version 0/1 container and stream directory facts. */
public final class XmdV1Directory {
    private XmdV1Directory() {
    }

    /** version, file/stream counts, string bytes and source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/version spans, container size, table end and stream range. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** stream offset and copied length. */
    public static long[] stream(byte[] blob, int index) {
        return nativeStream(blob, index);
    }

    /** first eight stream bytes as two little-endian 32-bit words. */
    public static long[] magic(byte[] blob, int index) {
        return nativeMagic(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeStream(byte[] blob, int index);

    private static native long[] nativeMagic(byte[] blob, int index);
}
