package com.wmmt.re6rr;

/** Shipped stage LOADLIST section blocks and NDWD stream descriptors. */
public final class LoadlistCatalog {
    private LoadlistCatalog() {
    }

    /** version, file count, block count, stream count, string bytes,
     * reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** first block and block count for one LOADLIST file. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** dump-relative LOADLIST path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** section id, source size, inflated size, wrap, first stream and count. */
    public static long[] block(byte[] blob, int index) {
        return nativeBlock(blob, index);
    }

    /** dump-relative section bin path, or null for a bad index. */
    public static String binPath(byte[] blob, int index) {
        return nativeBinPath(blob, index);
    }

    /** stream offset and size, or null for a bad index. */
    public static long[] stream(byte[] blob, int index) {
        return nativeStream(blob, index);
    }

    /** shipped ROAD_NAME label, or null for a bad index. */
    public static String streamName(byte[] blob, int index) {
        return nativeStreamName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeBlock(byte[] blob, int index);

    private static native String nativeBinPath(byte[] blob, int index);

    private static native long[] nativeStream(byte[] blob, int index);

    private static native String nativeStreamName(byte[] blob, int index);
}
