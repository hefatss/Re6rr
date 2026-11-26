package com.wmmt.re6rr;

/** Core-voice lookup table facts recovered from FUN_18001ed00. */
public final class VoiceCoreTableFacts {
    private VoiceCoreTableFacts() {
    }

    /** count, instance offset, stride, chain mode, lookup address. */
    public static long[] all() {
        return nativeAll();
    }

    private static native long[] nativeAll();
}
