package com.wmmt.re6rr;

/** Copied root setting.lua.gz gzip words, keys and integer rows. */
public final class SettingLuaGz {
    private SettingLuaGz() {
    }

    /** version, counts, string bytes, source/inflated totals and line count. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, compressed size, mtime, crc32 and inflated size. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied ASCII key name, or null for a bad index. */
    public static String key(byte[] blob, int index) {
        return nativeKey(blob, index);
    }

    /** copied integer literal, or null for a bad index. */
    public static String value(byte[] blob, int fileIndex, int keyIndex) {
        return nativeValue(blob, fileIndex, keyIndex);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeKey(byte[] blob, int index);

    private static native String nativeValue(byte[] blob, int fileIndex,
                                             int keyIndex);
}
