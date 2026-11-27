package com.wmmt.re6rr;

/** Recovered unlock/honor predicate schema: 13 types and ordered fields. */
public final class HonorSchema {
    private HonorSchema() {
    }

    /** type count, strings offset and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** Native type name, or null for an invalid type or blob. */
    public static String typeName(byte[] blob, int type) {
        return nativeType(blob, type);
    }

    /** Type row index for an exact name match; -1 if absent. */
    public static long findType(byte[] blob, String name) {
        return nativeFindType(blob, name);
    }

    /** Number of ordered fields, or -1 for an invalid type. */
    public static int fieldCount(byte[] blob, int type) {
        return nativeFieldCount(blob, type);
    }

    /** Field label, or null for an invalid type/field. */
    public static String field(byte[] blob, int type, int field) {
        return nativeField(blob, type, field);
    }

    /** field index for an exact label in one type; -1 if absent. */
    public static long findField(byte[] blob, int type, String name) {
        return nativeFindField(blob, type, name);
    }

    /** 20 values: object size, four field offsets, clear_bits range, ten
     *  Property slots and three native addresses for predicate type 1. */
    public static long[] type1Facts() {
        return nativeType1Facts();
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeType(byte[] blob, int type);

    private static native long nativeFindType(byte[] blob, String name);

    private static native int nativeFieldCount(byte[] blob, int type);

    private static native String nativeField(byte[] blob, int type, int field);

    private static native long nativeFindField(byte[] blob, int type,
                                                String name);

    private static native long[] nativeType1Facts();
}
