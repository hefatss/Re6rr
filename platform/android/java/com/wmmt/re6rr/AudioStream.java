package com.wmmt.re6rr;

/** Recovered BGM fade timing and stream-byte reservation arithmetic. */
public final class AudioStream {
    private AudioStream() {
    }

    public static final int FRAME_RATE = 60;
    public static final long STREAM_LIMIT = 0x20000000L;

    /** Frame delta at 60 fps, converted to whole milliseconds. */
    public static int fadeMs(int nowFrame, int maxFrame) {
        return nativeFadeMs(nowFrame, maxFrame);
    }

    /** New running stream-byte total, or -1 past the cap. */
    public static long reserve(long total, long size) {
        return nativeReserve(total, size);
    }

    private static native int nativeFadeMs(int nowFrame, int maxFrame);

    private static native long nativeReserve(long total, long size);
}
