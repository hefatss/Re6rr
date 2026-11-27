package com.wmmt.re6rr;

import java.util.Arrays;

/** Recovered extended-KeyOn status codes and 3D SE call-site facts. */
public final class VoiceDispatchFacts {
    private VoiceDispatchFacts() {
    }

    /** 32 values: 8 bank errors, 3 null errors, chain error, 3 modes,
     *  2 ext offsets, 2 ext sizes, 5 game layout words and 8 addresses. */
    public static long[] all() {
        return nativeAll();
    }

    public static long[] bankErrors() {
        return Arrays.copyOfRange(all(), 0, 8);
    }

    public static long[] nullErrors() {
        return Arrays.copyOfRange(all(), 8, 11);
    }

    public static long chainError() {
        return all()[11];
    }

    public static long[] chainModes() {
        return Arrays.copyOfRange(all(), 12, 15);
    }

    public static long[] extOffsets() {
        return Arrays.copyOfRange(all(), 15, 17);
    }

    public static long[] extSizes() {
        return Arrays.copyOfRange(all(), 17, 19);
    }

    public static long[] gameLayout() {
        return Arrays.copyOfRange(all(), 19, 24);
    }

    public static long[] addresses() {
        return Arrays.copyOfRange(all(), 24, 32);
    }

    /** 21 values: 6 plain wrapper addresses, 6 point wrapper addresses,
     *  2 line wrapper addresses, 3 extended flags, 3 position float counts
     *  and the secondary vector byte count. Zero means the group has no
     *  such argument; no wrapper is called. */
    public static long[] keyOnUsers() {
        return nativeKeyOnUsers();
    }

    private static native long[] nativeAll();

    private static native long[] nativeKeyOnUsers();
}
