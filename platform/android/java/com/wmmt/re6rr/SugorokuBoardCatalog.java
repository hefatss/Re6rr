package com.wmmt.re6rr;

/** Structural facts from the ghost-expedition sugoroku Lua tables. */
public final class SugorokuBoardCatalog {
    private SugorokuBoardCatalog() {
    }

    /** version, category/stage/page/function counts, item/square totals and
     * string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** copied name span, group/id counts and id range. */
    public static long[] category(byte[] blob, int index) {
        return nativeCategory(blob, index);
    }

    /** stage, page, square count, seven token counts and six reward counts. */
    public static long[] page(byte[] blob, int index) {
        return nativePage(blob, index);
    }

    /** copied Lua function name, or null for a bad index. */
    public static String function(byte[] blob, int index) {
        return nativeFunction(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeCategory(byte[] blob, int index);

    private static native long[] nativePage(byte[] blob, int index);

    private static native String nativeFunction(byte[] blob, int index);
}
