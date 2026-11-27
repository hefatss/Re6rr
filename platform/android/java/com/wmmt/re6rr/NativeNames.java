package com.wmmt.re6rr;

/** Shipped native pointer-name tables packed into an R6NAM blob. */
public final class NativeNames {
    private NativeNames() {
    }

    public static final int SEQUENCE = 0;
    public static final int TK_ARI = 1;
    public static final int STAGE_TIME = 2;
    public static final int TIPS_END = 3;
    public static final int FLASH = 4;
    public static final int PARTS = 5;
    public static final int HONOR = 6;
    public static final int CHECK_HONOR = 7;
    public static final int VINYL_BLEND = 8;

    /** 20 values: nine counts, nine offsets, strings offset and size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Resolved name, or null for an invalid kind/index or blob. */
    public static String name(byte[] blob, int kind, int index) {
        return nativeName(blob, kind, index);
    }

    /** first row index with an exact name; -1 if absent. */
    public static long find(byte[] blob, int kind, String name) {
        return nativeFind(blob, kind, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int kind, int index);

    private static native long nativeFind(byte[] blob, int kind,
                                           String name);
}
