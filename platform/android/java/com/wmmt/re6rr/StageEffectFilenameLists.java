package com.wmmt.re6rr;

/** Copied stage-effect filename-list paths and .lua basenames. */
public final class StageEffectFilenameLists {
    private StageEffectFilenameLists() {
    }

    /** version, file/name counts and string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, source byte size and copied name count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied .lua basename, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);
}
