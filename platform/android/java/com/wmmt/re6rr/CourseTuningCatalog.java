package com.wmmt.re6rr;

/** Copied course tuning integers and ASCII GID/ramp/stage symbol names. */
public final class CourseTuningCatalog {
    private CourseTuningCatalog() {
    }

    /** version, file count, ramp/TA row counts, string bytes, source size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path/global spans, source size, lines, row base and row count. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** copied table global, or null for a bad index. */
    public static String global(byte[] blob, int index) {
        return nativeGlobal(blob, index);
    }

    /** normal/extreme values and gid/name/alias spans. */
    public static long[] rampRow(byte[] blob, int index) {
        return nativeRampRow(blob, index);
    }

    /** section value and gid/name spans. */
    public static long[] taRow(byte[] blob, int index) {
        return nativeTaRow(blob, index);
    }

    public static String rampGid(byte[] blob, int index) {
        return nativeRampGid(blob, index);
    }

    public static String rampName(byte[] blob, int index) {
        return nativeRampName(blob, index);
    }

    public static String rampAlias(byte[] blob, int index) {
        return nativeRampAlias(blob, index);
    }

    public static String taGid(byte[] blob, int index) {
        return nativeTaGid(blob, index);
    }

    public static String taName(byte[] blob, int index) {
        return nativeTaName(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native String nativeGlobal(byte[] blob, int index);

    private static native long[] nativeRampRow(byte[] blob, int index);

    private static native long[] nativeTaRow(byte[] blob, int index);

    private static native String nativeRampGid(byte[] blob, int index);

    private static native String nativeRampName(byte[] blob, int index);

    private static native String nativeRampAlias(byte[] blob, int index);

    private static native String nativeTaGid(byte[] blob, int index);

    private static native String nativeTaName(byte[] blob, int index);
}
