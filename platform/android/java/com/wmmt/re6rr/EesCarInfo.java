package com.wmmt.re6rr;

/** int32 car_info id from one 0x8c-byte EES record. */
public final class EesCarInfo {
    private EesCarInfo() {
    }

    public static final int STRIDE = 0x8C;

    /** One-element array with the record id, or null for invalid input. */
    public static int[] read(byte[] raw, int offset) {
        return nativeRead(raw, offset);
    }

    private static native int[] nativeRead(byte[] raw, int offset);
}
