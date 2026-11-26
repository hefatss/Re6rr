package com.wmmt.re6rr;

/** Read and write the 32 chained-voice state records of 52 f32 slots each. */
public final class VoiceChain {
    private VoiceChain() {
    }

    public static final int COUNT = 0x20;
    public static final int STRIDE = 0xD0;
    public static final int FLOATS = 0x34;

    /** Copy the 52 f32 slots of one record as doubles. */
    public static double[] read(byte[] data, int index) {
        return nativeRead(data, index);
    }

    /** Return a copy of the full buffer with one record replaced. */
    public static byte[] write(byte[] data, int index, double[] values) {
        return nativeWrite(data, index, values);
    }

    /** Apply 52 state slots to a fresh core voice and copy its bytes back. */
    public static byte[] apply(double[] values) {
        return nativeApply(values);
    }

    private static native double[] nativeRead(byte[] data, int index);

    private static native byte[] nativeWrite(byte[] data, int index,
                                             double[] values);

    private static native byte[] nativeApply(double[] values);
}
