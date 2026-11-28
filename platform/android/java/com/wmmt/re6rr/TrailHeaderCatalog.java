package com.wmmt.re6rr;

/** Copied Enma trail header words and ASCII link names. */
public final class TrailHeaderCatalog {
    private TrailHeaderCatalog() {
    }

    /** version, counts, source size, record shape and marker word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** path span, size, links, name span, marker, record count and trailer. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied source path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** name span and source offset. */
    public static long[] name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** copied link name, or null for a bad index. */
    public static String nameText(byte[] blob, int index) {
        return nativeNameText(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeName(byte[] blob, int index);

    private static native String nativeNameText(byte[] blob, int index);
}
