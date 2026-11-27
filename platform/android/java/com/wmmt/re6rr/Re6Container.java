package com.wmmt.re6rr;

/** Bounded read-only view of an inflated XMD.001 stream table.
 *
 * The blob is the inflated container; stream bytes are copied out so no
 * native pointer crosses the JNI boundary. Observed shipped tags are NDWD
 * (`.mdl`) and NTWD (`.tex`); the gap before the first stream is not decoded.
 */
public final class Re6Container {
    private Re6Container() {
    }

    /** version, stream count; null on error. */
    public static long[] header(byte[] blob) {
        return nativeHeader(blob);
    }

    /** offset, size of one stream; null on bad index or container. */
    public static long[] stream(byte[] blob, int index) {
        return nativeStream(blob, index);
    }

    /** First four bytes of a stream, normally ASCII NDWD or NTWD. */
    public static byte[] tag(byte[] blob, int index) {
        return nativeTag(blob, index);
    }

    /** Copied stream bytes for Re6Texture / Re6MeshRecords. */
    public static byte[] streamBytes(byte[] blob, int index) {
        return nativeStreamBytes(blob, index);
    }

    private static native long[] nativeHeader(byte[] blob);
    private static native long[] nativeStream(byte[] blob, int index);
    private static native byte[] nativeTag(byte[] blob, int index);
    private static native byte[] nativeStreamBytes(byte[] blob, int index);
}
