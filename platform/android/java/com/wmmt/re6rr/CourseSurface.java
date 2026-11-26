package com.wmmt.re6rr;

/** Surface class inferred from shipped LOADLIST road names. */
public final class CourseSurface {
    private CourseSurface() {
    }

    public static final int UNKNOWN = -1;
    public static final int ROAD = 0;
    public static final int GRASS = 1;
    public static final int GRAVEL = 2;

    /** 0 road, 1 grass, 2 gravel, or -1 when no token matches. */
    public static int classify(String name) {
        return nativeClassify(name);
    }

    private static native int nativeClassify(String name);
}
