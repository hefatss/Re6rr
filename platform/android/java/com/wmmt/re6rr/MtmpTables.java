package com.wmmt.re6rr;

/** Raw SCALE and OBJECT lines from the shipped .MTMP stage-effect tables. */
public final class MtmpTables {
    private MtmpTables() {
    }

    /** version, file count, object count and string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** file size, first object and object count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** dump-relative path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** SCALE value without the prefix, or null for a bad index. */
    public static String scale(byte[] blob, int index) {
        return nativeScale(blob, index);
    }

    /** tab-separated OBJECT fields without the prefix, or null if absent. */
    public static String object(byte[] blob, int index) {
        return nativeObject(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeScale(byte[] blob, int index);

    private static native String nativeObject(byte[] blob, int index);
}
