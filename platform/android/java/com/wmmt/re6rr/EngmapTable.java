package com.wmmt.re6rr;

import java.util.Arrays;

/** WM4_ENGMAP engine sound to group pairs. */
public final class EngmapTable {
    private EngmapTable() {
    }

    /** First value is the entry count, followed by 320 engine_sound/group pairs.
     *  Null on a malformed or conflicting table. */
    public static long[] parse(byte[] raw) {
        return nativeParse(raw);
    }

    public static long[] pairs(long[] parsed) {
        return parsed == null ? null
                              : Arrays.copyOfRange(parsed, 1, parsed.length);
    }

    private static native long[] nativeParse(byte[] raw);
}
