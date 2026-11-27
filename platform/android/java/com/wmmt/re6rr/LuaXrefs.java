package com.wmmt.re6rr;

/** Shipped Lua names mapped to native function and pointer-table references. */
public final class LuaXrefs {
    private LuaXrefs() {
    }

    public static final int VIA_CODE = 0;
    public static final int VIA_TABLE = 1;
    public static final int VIA_POINTER = 2;
    public static final int KIND_STRINGS = 0;
    public static final int KIND_POINTER = 1;
    public static final int HIT_FUNC = 0;
    public static final int HIT_TABLE = 1;
    public static final int HIT_USER = 2;

    /** count, strings offset and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** row index for an exact Lua name match; -1 if absent. */
    public static long find(byte[] blob, String name) {
        return nativeFind(blob, name);
    }

    /** via, function count and table count; null for an invalid index. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** Function RVAs in native order. */
    public static long[] funcs(byte[] blob, int index) {
        return nativeFuncs(blob, index);
    }

    /** Flat table triples: rva, kind and user count. */
    public static long[] tables(byte[] blob, int index) {
        return nativeTables(blob, index);
    }

    /** Function RVAs that load one pointer table. */
    public static long[] users(byte[] blob, int index, int table) {
        return nativeUsers(blob, index, table);
    }

    /** Flat reverse-hit groups of (row, kind, which, item), stored order;
     *  kind is HIT_FUNC, HIT_TABLE or HIT_USER. Null when absent/invalid. */
    public static long[] findRva(byte[] blob, long rva) {
        if (rva < 0 || rva > 0xFFFFFFFFL) {
            return null;
        }
        return nativeFindRva(blob, rva);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long nativeFind(byte[] blob, String name);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native long[] nativeFuncs(byte[] blob, int index);

    private static native long[] nativeTables(byte[] blob, int index);

    private static native long[] nativeUsers(byte[] blob, int index, int table);

    private static native long[] nativeFindRva(byte[] blob, long rva);
}
