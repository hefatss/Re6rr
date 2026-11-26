package com.wmmt.re6rr;

/** Read the sys::Sound::Impl bank, loop and positional SE arrays. */
public final class SoundDispatch {
    private SoundDispatch() {
    }

    public static final int BANK_STRIDE = 0x20;
    public static final int BANK_STATE_READY = 3;
    public static final int REQUEST_COUNT = 0x22;
    public static final int LOOP_SLOT_SCENE = 0x21;
    public static final int LOOP_STRIDE = 0x08;
    public static final int POSITIONAL_STRIDE = 0x24;

    /** handle, state, ready. */
    public static long[] bank(byte[] data, int index) {
        return nativeBank(data, index);
    }

    /** flag, tone for one SE loop request slot. */
    public static long[] loop(byte[] data, int index) {
        return nativeLoop(data, index);
    }

    /** bank, tone, frames, x, y, z for one positional SE record. */
    public static double[] positional(byte[] data, int index) {
        return nativePositional(data, index);
    }

    private static native long[] nativeBank(byte[] data, int index);

    private static native long[] nativeLoop(byte[] data, int index);

    private static native double[] nativePositional(byte[] data, int index);
}
