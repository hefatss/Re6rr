package com.wmmt.re6rr;

/** Named fields of one 0x180-byte EES car_disp record. */
public final class EesCarDisp {
    private EesCarDisp() {
    }

    public static final int STRIDE = 0x180;
    public static final String[] NAMES = {
        "car_id", "flags", "matrix0", "matrix1", "matrix2", "matrix3",
        "matrix4", "matrix5", "matrix6", "matrix7", "matrix8", "matrix9",
        "matrix10", "matrix11", "matrix12", "matrix13", "matrix14",
        "matrix15", "yaw", "yaw_units"
    };

    /** 20 values in NAMES order, or null for invalid bytes or offset. */
    public static double[] read(byte[] raw, int offset) {
        return nativeRead(raw, offset);
    }

    private static native double[] nativeRead(byte[] raw, int offset);
}
