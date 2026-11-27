package com.wmmt.re6rr;

/** XMD.001 header facts from the shipped .TEX and .MDL assets. */
public final class XmdAssets {
    private XmdAssets() {
    }

    /** version, file count, stream count and string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** source size, inflated size, ext, wrap, gzip flags/mtime/xfl_os/ISIZE,
     * XMD version, first stream and stream count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** dump-relative path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** stream offset and size, or null for a bad index/local pair. */
    public static long[] stream(byte[] blob, int index, int local) {
        return nativeStream(blob, index, local);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeStream(byte[] blob, int index,
                                              int local);
}
