package com.wmmt.re6rr;

/** Shipped Environment.Lua value inventory and per-dir facts. */
public final class SceneEnvStats {
    private SceneEnvStats() {
    }

    /** dirs, present, actor slots, present slots, nonzero, unique actors,
     * actor min/max, stages, unique stages, stage min/max and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** present, stage, stage_root, stage_day, cam_id and four actor values. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** Ordinal of one ESeries_* directory name, or -1 when absent. */
    public static int find(byte[] blob, String name) {
        return nativeFind(blob, name);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String name);
}
