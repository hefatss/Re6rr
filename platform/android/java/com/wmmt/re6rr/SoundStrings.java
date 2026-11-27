package com.wmmt.re6rr;

/** Read nuSound2 bank or tone string tables from caller-owned bytes. */
public final class SoundStrings {
    private SoundStrings() {
    }

    public static final int BANK = 0;
    public static final int TONE = 1;

    /** version, bank id, count, size, name size, path size, rows offset, row size. */
    public static long[] header(byte[] blob, int kind) {
        return nativeHeader(blob, kind);
    }

    /** name, value; value is an empty string for bank tables. */
    public static String[] row(byte[] blob, int kind, int index) {
        return nativeRow(blob, kind, index);
    }

    /** Bank id for bank tables, 0 for tone tables, -1 on invalid input. */
    public static long rowId(byte[] blob, int kind, int index) {
        return nativeRowId(blob, kind, index);
    }

    /** first row index with an exact table name; -1 if absent. */
    public static long find(byte[] blob, int kind, String name) {
        return nativeFind(blob, kind, name);
    }

    private static native long[] nativeHeader(byte[] blob, int kind);

    private static native long nativeFind(byte[] blob, int kind, String name);

    private static native String[] nativeRow(byte[] blob, int kind, int index);

    private static native long nativeRowId(byte[] blob, int kind, int index);
}
