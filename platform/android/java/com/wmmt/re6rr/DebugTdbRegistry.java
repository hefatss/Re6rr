package com.wmmt.re6rr;

/** Copied course-debug TDB ids, names, blink names and accessor names. */
public final class DebugTdbRegistry {
    private DebugTdbRegistry() {
    }

    /** version, counts, string bytes and source byte totals. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source byte size and pair count for one TDB file. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** id, decimal comment and copied name span for one row. */
    public static long[] pair(byte[] blob, int index) {
        return nativePair(blob, index);
    }

    /** copied blink model name, or null for a bad index. */
    public static String blink(byte[] blob, int index) {
        return nativeBlink(blob, index);
    }

    /** copied Lua accessor name, or null for a bad index. */
    public static String accessor(byte[] blob, int index) {
        return nativeAccessor(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativePair(byte[] blob, int index);

    private static native String nativeBlink(byte[] blob, int index);

    private static native String nativeAccessor(byte[] blob, int index);
}
