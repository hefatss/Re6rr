package com.wmmt.re6rr;

/** Ordered per-car Lua script paths from the shipped loader. */
public final class ContextPaths {
    private ContextPaths() {
    }

    /** 12 slash-separated relative paths: tire, position, shader,
     *  specification, colour, in load order. Null for invalid names. The host
     *  skips paths that do not exist in the mounted dump. */
    public static String[] list(String car, String model) {
        return nativeList(car, model);
    }

    private static native String[] nativeList(String car, String model);
}
