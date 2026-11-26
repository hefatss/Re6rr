package com.wmmt.re6rr;

/** Shipped executable and source path strings as copied data. */
public final class PathStrings {
    private PathStrings() {
    }

    /** version, group count, string count and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** group kind (0 = executable, 1 = source), count and first index. */
    public static long[] group(byte[] blob, int index) {
        return nativeGroup(blob, index);
    }

    public static String get(byte[] blob, int index) {
        return nativeGet(blob, index);
    }

    public static String groupGet(byte[] blob, int groupIndex,
                                  int localIndex) {
        return nativeGroupGet(blob, groupIndex, localIndex);
    }

    /** group, local and global indexes of the first exact match; null if none. */
    public static long[] find(byte[] blob, String text) {
        return nativeFind(blob, text);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeGroup(byte[] blob, int index);

    private static native String nativeGet(byte[] blob, int index);

    private static native String nativeGroupGet(byte[] blob, int groupIndex,
                                                int localIndex);

    private static native long[] nativeFind(byte[] blob, String text);
}
