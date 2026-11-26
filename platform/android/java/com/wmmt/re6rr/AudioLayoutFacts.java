package com.wmmt.re6rr;

import java.util.Arrays;

/** Recovered bank-registration and voice/meta table offsets and limits. */
public final class AudioLayoutFacts {
    private AudioLayoutFacts() {
    }

    /** 17 values: 5 slot fields, 3 cleanup-record fields, reserve, limit,
     *  3 version bytes and 4 voice/meta fields. */
    public static long[] all() {
        return nativeAll();
    }

    public static long[] bankSlots() {
        return Arrays.copyOfRange(all(), 0, 5);
    }

    public static long[] cleanupRecord() {
        return Arrays.copyOfRange(all(), 5, 8);
    }

    public static long[] stream() {
        return Arrays.copyOfRange(all(), 8, 10);
    }

    public static long[] version() {
        return Arrays.copyOfRange(all(), 10, 13);
    }

    public static long[] voiceMeta() {
        return Arrays.copyOfRange(all(), 13, 17);
    }

    private static native long[] nativeAll();
}
