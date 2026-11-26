package com.wmmt.re6rr;

/** FUN_1401cc390 car_effect record copy into runtime field order. */
public final class EesCarEffect {
    private EesCarEffect() {
    }

    public static final int SOURCE_SIZE = 0xA0;
    public static final int COPY_SIZE = 0xE0;
    public static final int COPIES = 40;

    /** Copy one 0xa0 record into a 0xe0 runtime record, or null on bad input. */
    public static byte[] copy(byte[] record) {
        return nativeCopy(record);
    }

    private static native byte[] nativeCopy(byte[] record);
}
