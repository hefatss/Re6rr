package com.wmmt.re6rr;

/** Shipped luaL_Reg tables with copied names and function RVAs. */
public final class LuaRegTables {
    private LuaRegTables() {
    }

    /** version, table count, entry count, user count and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** rva, table size, stride, entry count, first entry, first user and
     * user count for one luaL_Reg table. */
    public static long[] table(byte[] blob, int index) {
        return nativeTable(blob, index);
    }

    /** name and function RVA for one global entry. */
    public static long entryFunc(byte[] blob, int index) {
        return nativeEntryFunc(blob, index);
    }

    public static String entryName(byte[] blob, int index) {
        return nativeEntryName(blob, index);
    }

    public static long tableEntryFunc(byte[] blob, int tableIndex,
                                      int localIndex) {
        return nativeTableEntryFunc(blob, tableIndex, localIndex);
    }

    public static String tableEntryName(byte[] blob, int tableIndex,
                                        int localIndex) {
        return nativeTableEntryName(blob, tableIndex, localIndex);
    }

    public static long user(byte[] blob, int index) {
        return nativeUser(blob, index);
    }

    /** table, local and global indexes of the first exact match; null if none. */
    public static long[] find(byte[] blob, String name) {
        return nativeFind(blob, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeTable(byte[] blob, int index);

    private static native long nativeEntryFunc(byte[] blob, int index);

    private static native String nativeEntryName(byte[] blob, int index);

    private static native long nativeTableEntryFunc(byte[] blob, int tableIndex,
                                                    int localIndex);

    private static native String nativeTableEntryName(byte[] blob,
                                                      int tableIndex,
                                                      int localIndex);

    private static native long nativeUser(byte[] blob, int index);

    private static native long[] nativeFind(byte[] blob, String name);
}
