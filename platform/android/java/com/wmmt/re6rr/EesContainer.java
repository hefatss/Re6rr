package com.wmmt.re6rr;

/** Header and typed arrays of an EventScene2 .EES container. */
public final class EesContainer {
    private EesContainer() {
    }

    public static final int CAM = 0;
    public static final int CAR = 1;
    public static final int CAMERA_INFO = 0;
    public static final int CAMERA_DATA = 1;
    public static final int CAR_DISP = 2;
    public static final int CAR_EFFECT = 3;
    public static final int CAR_INFO = 4;

    /** 22 ints: kind, version, fileSize, count, effectCount, headerSize,
     *  arrayCount, then name/count/stride/offset/size for three arrays.
     *  Unused car/cam fields are zero. Null on a malformed container. */
    public static int[] parse(byte[] raw) {
        return nativeParse(raw);
    }

    private static native int[] nativeParse(byte[] raw);
}
