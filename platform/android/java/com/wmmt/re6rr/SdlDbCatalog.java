package com.wmmt.re6rr;

/** Copied SDL controller database lines and row tokens. */
public final class SdlDbCatalog {
    private SdlDbCatalog() {
    }

    /** version, counts, source facts and path span. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied source path, or null for a bad blob. */
    public static String path(byte[] blob) {
        return nativePath(blob);
    }

    /** text span, kind and source line. */
    public static long[] line(byte[] blob, int index) {
        return nativeLine(blob, index);
    }

    /** copied verbatim line; empty for a blank line. */
    public static String lineText(byte[] blob, int index) {
        return nativeLineText(blob, index);
    }

    /** id/name/platform spans, field count and source line. */
    public static long[] row(byte[] blob, int index) {
        return nativeRow(blob, index);
    }

    /** row field 0=id, 1=name, 2=platform. */
    public static String fieldText(byte[] blob, int index, int field) {
        return nativeFieldText(blob, index, field);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeLine(byte[] blob, int index);

    private static native String nativeLineText(byte[] blob, int index);

    private static native long[] nativeRow(byte[] blob, int index);

    private static native String nativeFieldText(byte[] blob, int index,
                                                 int field);
}
