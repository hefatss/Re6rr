package com.wmmt.re6rr;

/** Validate the shipped Sound::Initialize config and report Impl vector sizes. */
public final class SoundInit {
    private SoundInit() {
    }

    public static final int CONFIG_SIZE = 0x28;
    public static final int IMPL_SIZE = 0x98;
    public static final int CONFIG_BIN_OFFSET = 0x10;
    public static final int CONFIG_3D_OFFSET = 0x18;
    public static final int CORE_INIT_OFFSET = 0x20;

    /** bankNum, reqidNum, streamNum, three opaque pointer slots,
     *  bank/request/stream vector bytes and the Impl size. */
    public static long[] parse(byte[] config) {
        return nativeParse(config);
    }

    private static native long[] nativeParse(byte[] config);
}
