package com.wmmt.re6rr;

/** Header and array facts from the shipped .EES scene files. */
public final class EesInventory {
    private EesInventory() {
    }

    /** version, file count, array count and string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** file size, kind, version, count, effect count, header size,
     * first array and array count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** scene-relative path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied array name, or null for a bad index. */
    public static String arrayName(byte[] blob, int index) {
        return nativeArrayName(blob, index);
    }

    /** array count, stride, offset and size, or null for a bad index. */
    public static long[] array(byte[] blob, int index) {
        return nativeArray(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeArrayName(byte[] blob, int index);

    private static native long[] nativeArray(byte[] blob, int index);
}
