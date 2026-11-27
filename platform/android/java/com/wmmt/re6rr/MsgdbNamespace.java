package com.wmmt.re6rr;

/** Complete shipped MessageID namespace with source offsets and groups. */
public final class MsgdbNamespace {
    private MsgdbNamespace() {
    }

    /** version, key count, group count, string bytes, msgdb size and the
     * drive_story_ subset count. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied ASCII MessageID, or null for a bad index. */
    public static String key(byte[] blob, int index) {
        return nativeKey(blob, index);
    }

    /** first exact-match row, or -1 when absent. */
    public static int find(byte[] blob, String key) {
        if (key == null) {
            return -1;
        }
        return nativeFind(blob, key);
    }

    /** byte offset in msgdb.lua and group index. */
    public static long[] fact(byte[] blob, int index) {
        return nativeFact(blob, index);
    }

    /** copied four-character group name, or null for a bad index. */
    public static String group(byte[] blob, int index) {
        return nativeGroup(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeKey(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String key);

    private static native long[] nativeFact(byte[] blob, int index);

    private static native String nativeGroup(byte[] blob, int index);
}
