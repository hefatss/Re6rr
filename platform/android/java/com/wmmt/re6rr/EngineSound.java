package com.wmmt.re6rr;

/** Read-only lookup of packed engine-sound mappings and layer envelopes. */
public final class EngineSound {
    private EngineSound() {
    }

    /** mapping count, sound count, tunes per car, layer count. */
    public static int[] header(byte[] data) {
        return nativeHeader(data);
    }

    /** car type, tune, group, engine sound, then 16 layer tones. */
    public static int[] find(byte[] data, int carType, int tune) {
        return nativeFind(data, carType, tune);
    }

    /** layer, source, flags, index, tone, 5 envelope values, rpm limit,
     *  scale and base. */
    public static double[] layer(byte[] data, int sound, int index) {
        return nativeLayer(data, sound, index);
    }

    private static native int[] nativeHeader(byte[] data);
    private static native int[] nativeFind(byte[] data, int carType, int tune);
    private static native double[] nativeLayer(byte[] data, int sound,
                                               int index);
}
