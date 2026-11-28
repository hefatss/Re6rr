package com.wmmt.re6rr;

/** Copied event-scene hide-clip model names and accessor name. */
public final class EventSceneHideClip {
    private EventSceneHideClip() {
    }

    /** version, name count, string bytes and two source byte sizes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied model name, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied Lua accessor name, or null for a bad blob. */
    public static String accessor(byte[] blob) {
        return nativeAccessor(blob);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native String nativeAccessor(byte[] blob);
}
