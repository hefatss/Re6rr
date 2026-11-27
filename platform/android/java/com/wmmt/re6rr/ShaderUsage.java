package com.wmmt.re6rr;

/** Shipped SHDR cbuffer and texture/sampler usage maps. */
public final class ShaderUsage {
    public static final int VERTEX = 0;
    public static final int PIXEL = 1;

    private ShaderUsage() {
    }

    /** version, record/uniform/resource/declaration counts and strings size. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** name offset, stage, uniform/resource/declaration spans, dynamic counts. */
    public static long[] record(byte[] blob, int index) {
        return nativeRecord(blob, index);
    }

    /** Shipped shader file name for one record, or null on bad input. */
    public static String name(byte[] blob, int index) {
        return nativeName(blob, index);
    }

    /** First record for an exact shader name and stage, or -1 when absent. */
    public static int find(byte[] blob, String name, int stage) {
        return nativeFind(blob, name, stage);
    }

    /** {uniform name, decimal operand count}; null on bad input. */
    public static String[] uniform(byte[] blob, int record, int index) {
        return nativeUniform(blob, record, index);
    }

    /** {resource or sampler key, decimal operand count}; null on bad input. */
    public static String[] resource(byte[] blob, int record, int index) {
        return nativeResource(blob, record, index);
    }

    /** {index, count} for the first exact uniform, or null when absent. */
    public static long[] findUniform(byte[] blob, int record, String name) {
        return nativeFindUniform(blob, record, name);
    }

    /** {index, count} for the first exact resource key, or null when absent. */
    public static long[] findResource(byte[] blob, int record, String name) {
        return nativeFindResource(blob, record, name);
    }

    /** DCL_RESOURCE/DCL_SAMPLER reflected name, or null on bad input. */
    public static String declared(byte[] blob, int record, int index) {
        return nativeDeclared(blob, record, index);
    }

    private static native long[] nativeHeader(byte[] blob);

    private static native long[] nativeRecord(byte[] blob, int index);

    private static native String nativeName(byte[] blob, int index);

    private static native int nativeFind(byte[] blob, String name, int stage);

    private static native String[] nativeUniform(byte[] blob, int record,
                                                 int index);

    private static native String[] nativeResource(byte[] blob, int record,
                                                  int index);

    private static native long[] nativeFindUniform(byte[] blob, int record,
                                                   String name);

    private static native long[] nativeFindResource(byte[] blob, int record,
                                                    String name);

    private static native String nativeDeclared(byte[] blob, int record,
                                                int index);
}
