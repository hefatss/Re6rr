package com.wmmt.re6rr;

/** Read-only view of the shipped config_3d.bin 3D sound sections. */
public final class Config3D {
    private Config3D() {
    }

    /** version[3], section count, section stride. */
    public static int[] header(byte[] data) {
        return nativeHeader(data);
    }

    /** Four global floats: db range, reference angle, order, blend. */
    public static double[] globals(byte[] data) {
        return nativeGlobals(data);
    }

    /** flags, db_start, angle (+90), db_end, raw[0..2] for one record. */
    public static double[] record(byte[] data, int section, int record) {
        return nativeRecord(data, section, record);
    }

    /** Six tail words of one section. */
    public static int[] tail(byte[] data, int section) {
        return nativeTail(data, section);
    }

    /** dB to amplitude using host libm; zero below the zero-dB floor. */
    public static double amplitude(double db, double zeroDb) {
        return nativeAmplitude(db, zeroDb);
    }

    private static native int[] nativeHeader(byte[] data);

    private static native double[] nativeGlobals(byte[] data);

    private static native double[] nativeRecord(byte[] data, int section,
                                                int record);

    private static native int[] nativeTail(byte[] data, int section);

    private static native double nativeAmplitude(double db, double zeroDb);
}
