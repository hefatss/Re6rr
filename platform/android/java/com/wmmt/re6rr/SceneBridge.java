package com.wmmt.re6rr;

/** Environment.Lua camid bridge and runtime camera record lookup. */
public final class SceneBridge {
    private SceneBridge() {
    }

    public static final int CAMID_OFFSET = 0x24;
    public static final int CONFIG_CAMID_OFFSET = 0x70;
    public static final int CONFIG_OFFSET = 0x740;
    public static final int CONTAINER_BASE = 0x2D78;
    public static final int CONTAINER_STRIDE = 0x1B0;
    public static final int CONTAINER_COUNT = 5;
    public static final int LOADER_CAMID = 0x48;
    public static final int RECORD_SIZE = 0x10;

    /** Copy scene +0x24 into config +0x70; config is updated in place.
     *  Returns the copied camid, or -1 on invalid buffers. */
    public static int writeCamid(byte[] scene, byte[] config) {
        return nativeWriteCamid(scene, config);
    }

    /** Camera container byte offset, or -1 for an out-of-range slot. */
    public static int containerOffset(int slot) {
        return nativeContainerOffset(slot);
    }

    /** First matching runtime camera record, or -1. */
    public static int runtimeCamera(byte[] records, int frame) {
        return nativeRuntimeCamera(records, frame);
    }

    private static native int nativeWriteCamid(byte[] scene, byte[] config);

    private static native int nativeContainerOffset(int slot);

    private static native int nativeRuntimeCamera(byte[] records, int frame);
}
