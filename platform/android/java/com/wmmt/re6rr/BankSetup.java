package com.wmmt.re6rr;

/** Read-only bank-registration view used before nuSound2 plays a .nub. */
public final class BankSetup {
    private BankSetup() {
    }

    /** version[3], tone count, data offset, data size, record table, has tones. */
    public static int[] header(byte[] data) {
        return nativeHeader(data);
    }

    /** length, data offset, format count for one tone. */
    public static double[] tone(byte[] data, int index) {
        return nativeTone(data, index);
    }

    private static native int[] nativeHeader(byte[] data);

    private static native double[] nativeTone(byte[] data, int index);
}
