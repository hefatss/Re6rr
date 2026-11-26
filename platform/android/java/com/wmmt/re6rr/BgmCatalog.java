package com.wmmt.re6rr;

/** Read-only lookup of the packed shipped BGM table. */
public final class BgmCatalog {
    private BgmCatalog() {
    }

    /** version, count, first id, string offset, string bytes. */
    public static int[] header(byte[] data) {
        return nativeHeader(data);
    }

    /** id, flags, name offset, path offset. */
    public static int[] findId(byte[] data, int id) {
        return nativeFindId(data, id);
    }

    /** Same four values as findId(), found by substring of the BGM name. */
    public static int[] findName(byte[] data, String name) {
        return nativeFindName(data, name);
    }

    /** NUL-terminated interned name or path. */
    public static String string(byte[] data, int offset) {
        return nativeString(data, offset);
    }

    private static native int[] nativeHeader(byte[] data);
    private static native int[] nativeFindId(byte[] data, int id);
    private static native int[] nativeFindName(byte[] data, String name);
    private static native String nativeString(byte[] data, int offset);
}
