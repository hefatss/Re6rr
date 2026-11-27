package com.wmmt.re6rr;

/** Recovered Enma SetDefault struct layouts and constant bytes. */
public final class EnmaDefaults {
    private EnmaDefaults() {
    }

    /** struct count, fields offset, data offset, strings offset and size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** max written byte and field count, or null for invalid index. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** struct row index for an exact name match; -1 if absent. */
    public static long findStruct(byte[] blob, String name) {
        return nativeFindStruct(blob, name);
    }

    /** field offset and byte count, or null for invalid index/field. */
    public static long[] field(byte[] blob, int index, int field) {
        return nativeField(blob, index, field);
    }

    /** Constant bytes written by one SetDefault field. */
    public static byte[] bytes(byte[] blob, int index, int field) {
        return nativeBytes(blob, index, field);
    }

    /** field index for an exact write offset; -1 if absent. */
    public static long findField(byte[] blob, int index, long offset) {
        return nativeFindField(blob, index, offset);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native long nativeFindStruct(byte[] blob, String name);

    private static native long[] nativeField(byte[] blob, int index, int field);

    private static native byte[] nativeBytes(byte[] blob, int index, int field);

    private static native long nativeFindField(byte[] blob, int index,
                                                long offset);
}
