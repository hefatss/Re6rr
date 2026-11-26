package com.wmmt.re6rr;

/** Read-only view of a compiled R6GL shader binding manifest. */
public final class GlslBindings {
    private final byte[] data;

    public GlslBindings(byte[] data) {
        if (data == null) {
            throw new IllegalArgumentException("manifest is null");
        }
        this.data = data;
    }

    public int count() {
        return nativeCount(data);
    }

    /** flags, cbuffers, samplers, cbuffer_first, name offset. */
    public int[] record(int index) {
        return nativeRecord(data, index);
    }

    public String name(int offset) {
        return nativeName(data, offset);
    }

    /** binding, name offset, size, slots, ubo, regions, region_first. */
    public int[] cbuffer(int record, int index) {
        return nativeCbuffer(data, record, index);
    }

    /** offset, size, kind, type. */
    public int[] region(int record, int cbuffer, int index) {
        return nativeRegion(data, record, cbuffer, index);
    }

    /** texture unit, texture name offset, sampler name offset. */
    public int[] sampler(int record, int index) {
        return nativeSampler(data, record, index);
    }

    /** internal format, format, type, width, height, RGBA8 byte size. */
    public static int[] textureUpload(int unit, int format, int width,
                                      int height) {
        return nativeTextureUpload(unit, format, width, height);
    }

    private static native int nativeCount(byte[] data);
    private static native int[] nativeRecord(byte[] data, int index);
    private static native String nativeName(byte[] data, int offset);
    private static native int[] nativeCbuffer(byte[] data, int record,
                                              int index);
    private static native int[] nativeRegion(byte[] data, int record,
                                             int cbuffer, int index);
    private static native int[] nativeSampler(byte[] data, int record,
                                              int index);
    private static native int[] nativeTextureUpload(int unit, int format,
                                                    int width, int height);
}
