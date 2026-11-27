package com.wmmt.re6rr;

/** Shipped course route rows and path-bin facts; no geometry is decoded. */
public final class CoursePaths {
    private CoursePaths() {
    }

    /** version, route count, ref count, file count and string bytes. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** file size and float32 triple count, or null for a bad index. */
    public static long[] file(byte[] blob, int index) {
        return nativeFile(blob, index);
    }

    /** relative path under data/course/path, or null for a bad index. */
    public static String path(byte[] blob, int index) {
        return nativePath(blob, index);
    }

    /** area id, loop, camera direction, first ref and ref count. */
    public static long[] route(byte[] blob, int index) {
        return nativeRoute(blob, index);
    }

    /** route MenuText, or null for a bad index. */
    public static String routeName(byte[] blob, int index) {
        return nativeRouteName(blob, index);
    }

    /** exact shipped `.bin` name at a global ref index. */
    public static String routeRef(byte[] blob, int index) {
        return nativeRouteRef(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeFile(byte[] blob, int index);

    private static native String nativePath(byte[] blob, int index);

    private static native long[] nativeRoute(byte[] blob, int index);

    private static native String nativeRouteName(byte[] blob, int index);

    private static native String nativeRouteRef(byte[] blob, int index);
}
