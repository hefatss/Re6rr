package com.wmmt.re6rr;

/** Read-only view of the nuSound2 bank registration slot scan. */
public final class BankSlots {
    private BankSlots() {
    }

    public static final int COUNT = 0x40;
    public static final int STRIDE = 0x804;
    public static final int TABLE_SIZE = 0x20100;

    /** First free slot index, or -1 when all slots are used or input is bad. */
    public static int find(byte[] slots) {
        return nativeFind(slots);
    }

    private static native int nativeFind(byte[] slots);
}
