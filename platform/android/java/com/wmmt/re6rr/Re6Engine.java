package com.wmmt.re6rr;

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

    /** Create a vehicle from the currently loaded car context. */
    public Vehicle createVehicle(String car, String model) {
        check();
        long vehicle = nativeVehicleFromLua(handle, car, model);
        if (vehicle == 0) {
            throw new IllegalStateException("vehicle init failed: " + lastError());
        }
        return new Vehicle(vehicle);
    }

    /** Vehicle with default parameters, independent of any Lua context. */
    public static Vehicle createVehicle() {
        long vehicle = nativeVehicleCreate();
        if (vehicle == 0) {
            throw new IllegalStateException("vehicle init failed");
        }
        return new Vehicle(vehicle);
    }

    /** State indices: x y z vx vy yaw yawRate speed rpm throttle brake steer
     *  gear odo wheelSpin. */
    public static final class Vehicle implements AutoCloseable {
        private long handle;

        private Vehicle(long handle) {
            this.handle = handle;
        }

        @Override
        public void close() {
            if (handle != 0) {
                nativeVehicleDestroy(handle);
                handle = 0;
            }
        }

        public int step(float throttle, float brake, float steer, int gear,
                        float dt) {
            if (handle == 0) {
                throw new IllegalStateException("vehicle closed");
            }
            return nativeVehicleStep(handle, throttle, brake, steer, gear, dt);
        }

        public float[] state() {
            if (handle == 0) {
                throw new IllegalStateException("vehicle closed");
            }
            return nativeVehicleState(handle);
        }
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
    private static native long nativeVehicleCreate();
    private static native long nativeVehicleFromLua(long handle, String car, String model);
    private static native void nativeVehicleDestroy(long handle);
    private static native int nativeVehicleStep(long handle, float throttle, float brake, float steer, int gear, float dt);
    private static native float[] nativeVehicleState(long handle);

    static {
        System.loadLibrary("r6engine");
    }
}
