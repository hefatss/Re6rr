package com.wmmt.re6rr;

/** Raw shipped string-to-RVA xrefs before Lua binding synthesis. */
public final class StringXrefs {
    private StringXrefs() {
    }

    /** version, instruction/string-ref/string totals, requested/found counts,
     * name/RVA counts, strings size and strings offset. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** first global RVA index and RVA count for one name. */
    public static long[] nameRange(byte[] blob, int index) {
        return nativeNameRange(blob, index);
    }

    public static long rva(byte[] blob, int index) {
        return nativeRva(blob, index);
    }

    public static long nameRva(byte[] blob, int nameIndex, int localIndex) {
        return nativeNameRva(blob, nameIndex, localIndex);
    }

    /** name index of the first exact match; -1 if absent. */
    public static long find(byte[] blob, String name) {
        return nativeFind(blob, name);
    }

    /** every global RVA index with that exact RVA, in stored order;
     *  null when absent or invalid. */
    public static long[] findRva(byte[] blob, long rva) {
        return nativeFindRva(blob, rva);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeNameRange(byte[] blob, int index);

    private static native long nativeRva(byte[] blob, int index);

    private static native long nativeNameRva(byte[] blob, int nameIndex,
                                             int localIndex);

    private static native long nativeFind(byte[] blob, String name);

    private static native long[] nativeFindRva(byte[] blob, long rva);
}
