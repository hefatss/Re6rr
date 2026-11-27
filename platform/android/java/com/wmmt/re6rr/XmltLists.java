package com.wmmt.re6rr;

/** Structural facts from shipped XMLT lists, seeds and field tags. */
public final class XmltLists {
    private XmltLists() {
    }

    /** version and file/list/seed/field/type/tag/string counts plus reserved. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** first list and list count for one XMLT file. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** dump-relative XMLT path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** type index, first seed/count and first field/count for one LIST. */
    public static long[] list(byte[] blob, int index) {
        return nativeList(blob, index);
    }

    /** copied LIST_TYPE name, or null for a bad index. */
    public static String type(byte[] blob, int index) {
        return nativeType(blob, index);
    }

    /** owning list index, first field and field count for one SEED. */
    public static long[] seed(byte[] blob, int index) {
        return nativeSeed(blob, index);
    }

    /** owning seed index and field tag index for one field occurrence. */
    public static long[] field(byte[] blob, int index) {
        return nativeField(blob, index);
    }

    /** copied field tag name, or null for a bad index. */
    public static String tag(byte[] blob, int index) {
        return nativeTag(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeList(byte[] blob, int index);

    private static native String nativeType(byte[] blob, int index);

    private static native long[] nativeSeed(byte[] blob, int index);

    private static native long[] nativeField(byte[] blob, int index);

    private static native String nativeTag(byte[] blob, int index);
}
