package com.wmmt.re6rr;

/** Copied facts from the shipped PE base relocation directory. */
public final class RelocInventory {
    private RelocInventory() {
    }

    /** version, directory RVA/size, section/block/entry counts and the
     * 16 per-type entry counts. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** section RVA and size, or null for a bad index. */
    public static long[] section(byte[] blob, int index) {
        return nativeSection(blob, index);
    }

    /** page RVA, block size, first entry, entry count and section index. */
    public static long[] block(byte[] blob, int index) {
        return nativeBlock(blob, index);
    }

    /** page offset, type, absolute RVA and owning block index. */
    public static long[] entry(byte[] blob, int index) {
        return nativeEntry(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeSection(byte[] blob, int index);

    private static native long[] nativeBlock(byte[] blob, int index);

    private static native long[] nativeEntry(byte[] blob, int index);
}
