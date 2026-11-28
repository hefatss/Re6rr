package com.wmmt.re6rr;

/** Header facts from shipped AMUpdater TGA graphics. */
public final class TgaInventoryCatalog {
    private TgaInventoryCatalog() {
    }

    /** version, file count, string bytes, total bytes and raw/RLE counts. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied path span, size, image kind, dimensions, bpp, descriptor,
     * pixel byte count and raw-size-exact flag. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative .tga path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);
}
