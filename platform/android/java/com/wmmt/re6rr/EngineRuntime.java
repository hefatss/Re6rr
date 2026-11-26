package com.wmmt.re6rr;

/** Evaluate the 16 engine layers from packed runtime and envelope blobs. */
public final class EngineRuntime {
    private EngineRuntime() {
    }

    /** Number of EMTIS sounds in the runtime blob. */
    public static int soundCount(byte[] runtime) {
        return nativeSoundCount(runtime);
    }

    /** State values in order: base[5], layerBase[16], throttle, floors[9],
     *  smooth34, smooth4f, smooth20, f134, f2d, sub, curveScale. */
    public static double[] evaluate(byte[] runtime, byte[] engineSound,
                                    int sound, int rpm, int current,
                                    int requestOffset, boolean flag,
                                    double[] values) {
        if (values == null || values.length != 38) {
            throw new IllegalArgumentException("state needs 38 values");
        }
        return nativeEvaluate(runtime, engineSound, sound, rpm, current,
                              requestOffset, flag, values);
    }

    /** Six values per layer: layer, source, tone, pitch, level, volume. */
    private static native double[] nativeEvaluate(byte[] runtime,
                                                  byte[] engineSound,
                                                  int sound, int rpm,
                                                  int current,
                                                  int requestOffset,
                                                  boolean flag,
                                                  double[] values);

    private static native int nativeSoundCount(byte[] runtime);
}
