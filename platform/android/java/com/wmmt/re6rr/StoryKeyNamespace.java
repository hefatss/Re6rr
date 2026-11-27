package com.wmmt.re6rr;

/** All shipped drive_story_* MessageIDs with observed native sources. */
public final class StoryKeyNamespace {
    private StoryKeyNamespace() {
    }

    /** version, key count, native count, string bytes, header size,
     * strings offset and reserved word. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied ASCII key, or null for a bad index. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** first exact-match row, or -1 when absent. */
    public static int find(byte[] blob, String name) {
        if (name == null) {
            return -1;
        }
        return nativeFind(blob, name);
    }

    /** source flag and table index, or null for a bad index. */
    public static long[] fact(byte[] blob, int index) {
        return nativeFact(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native String nativeName(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String name);

    private static native long[] nativeFact(byte[] blob, int index);
}
