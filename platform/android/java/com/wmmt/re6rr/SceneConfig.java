package com.wmmt.re6rr;

/** Environment.Lua scene packing and shipped native name resolution. */
public final class SceneConfig {
    private SceneConfig() {
    }

    public static final int CAR_NAMES = 0;
    public static final int STAGE_NAMES = 1;
    public static final int DAY_NAMES = 2;
    public static final int SCENE_SIZE = 0x28;

    /** Pack stage, stage root, stage day, camid and four actors. */
    public static byte[] pack(int stage, int stageRoot, int stageDay,
                              int camId, int[] actors) {
        return nativePack(stage, stageRoot, stageDay, camId, actors);
    }

    /** car count, stage count, day count, strings offset. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Resolved name, or null for an unmapped stage/day or invalid input. */
    public static String name(byte[] blob, int kind, int value) {
        return nativeName(blob, kind, value);
    }

    private static native byte[] nativePack(int stage, int stageRoot,
                                            int stageDay, int camId,
                                            int[] actors);

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int kind, int value);
}
