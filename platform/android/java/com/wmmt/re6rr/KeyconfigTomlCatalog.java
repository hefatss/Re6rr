package com.wmmt.re6rr;

/** Copied keyconfig.toml lines and kinds. */
public final class KeyconfigTomlCatalog {
    private KeyconfigTomlCatalog() {
    }

    /** version, counts, source bytes and path span. */
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
    public static String text(byte[] blob, int index) {
        return nativeText(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativePath(byte[] blob);

    private static native long[] nativeLine(byte[] blob, int index);

    private static native String nativeText(byte[] blob, int index);
}
