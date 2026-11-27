package com.wmmt.re6rr;

/** Structural facts from root FBK/GBK_W6W gzip banks. */
public final class WmbkBankCatalog {
    private WmbkBankCatalog() {
    }

    /** version, file count, record count, string bytes and size totals. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied gzip header words, byte spans and record range for one bank. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** copied dump-relative bank path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** file index, byte offset, magic, version and payload length. */
    public static long[] record(byte[] blob, int index) {
        return nativeRecord(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeRecord(byte[] blob, int index);
}
