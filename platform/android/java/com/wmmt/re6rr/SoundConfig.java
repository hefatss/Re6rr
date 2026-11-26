package com.wmmt.re6rr;

/** Header of the shipped data/sound/config.bin. */
public final class SoundConfig {
    private SoundConfig() {
    }

    public static final int HEADER_SIZE = 0x50;
    public static final int SECTIONS = 6;
    public static final int FLOAT_OFFSET = 0x14;
    public static final int PAIRS_OFFSET = 0x18;

    /** size, header size, float offset, six counts, six offsets. */
    public static long[] parse(byte[] data) {
        return nativeParse(data);
    }

    private static native long[] nativeParse(byte[] data);
}
