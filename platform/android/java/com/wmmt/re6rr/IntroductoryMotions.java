package com.wmmt.re6rr;

/** Copied introductory-motion names, waits and accessor names. */
public final class IntroductoryMotions {
    private IntroductoryMotions() {
    }

    /** version, row/name/function counts, string bytes and two frame scalars. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** two copied name spans and the wait frame. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** copied .MED name for slot 0 or 1, or null for a bad index. */
    public static String name(byte[] blob, int index, int slot) {
        return nativeName(blob, index, slot);
    }

    /** copied Lua accessor name, or null for a bad index. */
    public static String function(byte[] blob, int index) {
        return nativeFunction(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index, int slot);

    private static native String nativeFunction(byte[] blob, int index);
}
