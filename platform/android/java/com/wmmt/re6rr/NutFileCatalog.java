package com.wmmt.re6rr;

/** File-level NTWD/NTLX header facts from shipped .nut containers. */
public final class NutFileCatalog {
    private NutFileCatalog() {
    }

    /** version, file count, string bytes, source/inflated totals and counts. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied header words: path span, sizes, container, version, entries,
     * total, payload/descriptor sizes, packed words, gidx, payload offset and
     * exact-layout flag. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative .nut path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);
}
