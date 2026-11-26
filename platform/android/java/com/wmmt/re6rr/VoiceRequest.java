package com.wmmt.re6rr;

/** Build and inspect the recovered 0xa0-byte KeyOn voice request. */
public final class VoiceRequest {
    private VoiceRequest() {
    }

    public static final int SIZE = 0xA0;
    public static final int EXT_A_SIZE = 0x34;
    public static final int EXT_B_SIZE = 0x1C;

    /** Build a request; bank/tone/voice pointers stay zero on the native side. */
    public static byte[] build(int request, int bank, int tone, int bankInfo,
                               int chainTone, int extended,
                               byte[] extA, byte[] extB,
                               double volume, double pan, int flags,
                               double extraA, double extraB, double extraC) {
        return nativeBuild(request, bank, tone, bankInfo, chainTone, extended,
                           extA, extB, volume, pan, flags,
                           extraA, extraB, extraC);
    }

    /** request, bank, bankInfo, tone, chainTone, extended, reserved,
     *  volume, pan, flags, extraA, extraB, extraC. */
    public static double[] fields(byte[] data) {
        return nativeFields(data);
    }

    /** Copy ext_a when a is false, ext_b when true. */
    public static byte[] ext(byte[] data, boolean a) {
        return nativeExt(data, a);
    }

    private static native byte[] nativeBuild(int request, int bank, int tone,
                                             int bankInfo, int chainTone,
                                             int extended, byte[] extA,
                                             byte[] extB, double volume,
                                             double pan, int flags,
                                             double extraA, double extraB,
                                             double extraC);

    private static native double[] nativeFields(byte[] data);

    private static native byte[] nativeExt(byte[] data, boolean a);
}
