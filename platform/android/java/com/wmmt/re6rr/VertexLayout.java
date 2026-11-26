package com.wmmt.re6rr;

/** Read-only view of a compiled R6GV vertex-input layout. */
public final class VertexLayout {
    private final byte[] data;

    public VertexLayout(byte[] data) {
        if (data == null) {
            throw new IllegalArgumentException("layout is null");
        }
        this.data = data;
    }

    /** Number of reflected vertex attributes. */
    public int count() {
        return nativeCount(data);
    }

    /** shader name offset, location, semantic index, mask, semantic offset. */
    public int[] attrib(int index) {
        return nativeAttrib(data, index);
    }

    /** Same five values as attrib(), found by shader name and GLSL location. */
    public int[] find(String shader, int location) {
        return nativeFind(data, shader, location);
    }

    /** NUL-terminated interned shader or semantic name. */
    public String name(int offset) {
        return nativeName(data, offset);
    }

    private static native int nativeCount(byte[] data);
    private static native int[] nativeAttrib(byte[] data, int index);
    private static native int[] nativeFind(byte[] data, String shader,
                                           int location);
    private static native String nativeName(byte[] data, int offset);
}
