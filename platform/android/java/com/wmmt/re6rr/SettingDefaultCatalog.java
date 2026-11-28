package com.wmmt.re6rr;

/** Copied setting_default.lua row names, active flags and value tokens. */
public final class SettingDefaultCatalog {
    private SettingDefaultCatalog() {
    }

    /** version, counts, source bytes and line total. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied source path, or null for a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** name/value spans and active flag. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied m_* row name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied SettingConst token or hex literal. */
    public static String value(byte[] blob, int index) {
        return nativeValue(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeValue(byte[] blob, int index);
}
