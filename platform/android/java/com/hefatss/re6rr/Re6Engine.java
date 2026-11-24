package com.hefatss.re6rr;

/** Java side of the JNI bridge. Asset lookup and gzip container reads belong
 *  in the Android platform layer; this class only marshals bytes into the C
 *  core and reads results back.
 */
public final class Re6Engine implements AutoCloseable {
    private long handle;

    public Re6Engine() {
        handle = nativeCreate();
        if (handle == 0) {
            throw new IllegalStateException("r6_engine_init failed");
        }
    }

    @Override
    public void close() {
        if (handle != 0) {
            nativeDestroy(handle);
            handle = 0;
        }
    }

    /** Load one ordered script chunk. name is used in Lua error messages. */
    public int loadScript(String name, byte[] chunk) {
        check();
        return nativeLoadScript(handle, name, chunk);
    }

    /** Load an ordered context bundle; names and chunks must align. */
    public int loadContext(String[] names, byte[][] chunks) {
        check();
        return nativeLoadContext(handle, names, chunks);
    }

    /** Returns three floats, or null when the native call failed. */
    public float[] callVec3(String function, String key, int index) {
        check();
        return nativeCallVec3(handle, function, key, index);
    }

    public double callNumber(String function) {
        check();
        return nativeCallNumber(handle, function);
    }

    public boolean hasFunction(String function) {
        check();
        return nativeHasFunction(handle, function);
    }

    /** Inflate a gzip member without touching the filesystem. */
    public static byte[] inflateGzip(byte[] data) {
        return nativeInflateGzip(data);
    }

    public String lastError() {
        check();
        return nativeLastError(handle);
    }

    private void check() {
        if (handle == 0) {
            throw new IllegalStateException("engine closed");
        }
    }

    private static native long nativeCreate();
    private static native void nativeDestroy(long handle);
    private static native int nativeLoadScript(long handle, String name, byte[] chunk);
    private static native int nativeLoadContext(long handle, String[] names, byte[][] chunks);
    private static native float[] nativeCallVec3(long handle, String name, String key, int index);
    private static native double nativeCallNumber(long handle, String name);
    private static native boolean nativeHasFunction(long handle, String name);
    private static native String nativeLastError(long handle);
    private static native byte[] nativeInflateGzip(byte[] data);

    static {
        System.loadLibrary("r6engine");
    }
}
