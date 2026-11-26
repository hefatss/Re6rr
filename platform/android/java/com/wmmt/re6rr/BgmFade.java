package com.wmmt.re6rr;

/** nuSound2 stream fade state at the offsets recovered from the shipped DLL. */
public final class BgmFade {
    private BgmFade() {
    }

    public static final int RECORD_SIZE = 0x2C4;
    public static final long INVALID_HANDLE = 0x8000000AL;
    public static final long NOT_PLAYING = 0x8000000BL;
    public static final long ALREADY_FADING = 0x80000000L;

    /** state, flag, mode, frames, step, volume, voice, channel, fader. */
    public static double[] read(byte[] stream) {
        return nativeRead(stream);
    }

    /** Begin a fade; on success the stream array is updated in place.
     *  Returns {status, voice id to stop}. */
    public static long[] begin(byte[] stream, int ms) {
        return nativeBegin(stream, ms);
    }

    private static native double[] nativeRead(byte[] stream);

    private static native long[] nativeBegin(byte[] stream, int ms);
}
