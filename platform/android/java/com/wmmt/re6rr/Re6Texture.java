package com.wmmt.re6rr;

/** NTWD/NTLX texture headers and RGBA8 decode for GLES upload. */
public final class Re6Texture {
    private Re6Texture() {
    }

    public static int count(byte[] data) {
        return nativeCount(data);
    }

    /** width, height, format, mip levels, flags, payload size. */
    public static int[] info(byte[] data, int index) {
        return nativeInfo(data, index);
    }

    /** expected size, face size, aligned level 0 bytes, declared levels,
     *  available levels and cube flag; null on invalid input. */
    public static long[] layout(byte[] data, int index) {
        return nativeLayout(data, index);
    }

    /** RGBA8 pixels for one mip level and cube face, or null on error. */
    public static byte[] decodeRgba(byte[] data, int index, int level,
                                    int face) {
        return nativeDecodeRgba(data, index, level, face);
    }

    private static native int nativeCount(byte[] data);
    private static native int[] nativeInfo(byte[] data, int index);
    private static native long[] nativeLayout(byte[] data, int index);
    private static native byte[] nativeDecodeRgba(byte[] data, int index,
                                                  int level, int face);
}
