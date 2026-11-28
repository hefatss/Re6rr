package com.wmmt.re6rr;

/** Copied Scene.Lua descriptor paths, strings and counts. */
public final class SceneDescriptors {
    private SceneDescriptors() {
    }

    /** version, file count and string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/root/environment spans, source size and two event counts. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied S_DATA_ROOT string, or null for a bad index. */
    public static String root(byte[] blob, int index) {
        return nativeRoot(blob, index);
    }

    /** copied S_ENVIRONMENT_DATA string, or null for a bad index. */
    public static String environment(byte[] blob, int index) {
        return nativeEnvironment(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeRoot(byte[] blob, int index);

    private static native String nativeEnvironment(byte[] blob, int index);
}
