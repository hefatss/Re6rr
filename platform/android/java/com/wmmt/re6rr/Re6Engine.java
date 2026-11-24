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

    /** Race with default rules: battle, Series01, 3 s countdown, one lap. */
    public static Race createRace() {
        return new Race(nativeRaceCreate(4, 3, 1, 0, 1.0e8f, 0.0f,
                                         3.0f, 1, 2.0f, 1.0f));
    }

    /** Race with explicit SConfigPlay-like rules. */
    public Race createRace(int mode, int stage, int course, int area,
                           float goalOdo, float timeLimit, float countdown,
                           int laps, float wrongWayLimit, float offroadFactor) {
        check();
        return new Race(nativeRaceCreate(mode, stage, course, area, goalOdo,
                                         timeLimit, countdown, laps,
                                         wrongWayLimit, offroadFactor));
    }

    /** Each course vertex is x y z halfWidth surface flags reserved pad. */
    public static final class Race implements AutoCloseable {
        private long handle;

        private Race(long handle) {
            if (handle == 0) {
                throw new IllegalStateException("race init failed");
            }
            this.handle = handle;
        }

        @Override
        public void close() {
            if (handle != 0) {
                nativeRaceDestroy(handle);
                handle = 0;
            }
        }

        /** vehicle is the 15-float array returned by Vehicle.state(). */
        public int step(float[] vertices, boolean closed, float[] vehicle,
                        float dt) {
            if (handle == 0) {
                throw new IllegalStateException("race closed");
            }
            if (vertices != null && vertices.length % 8 != 0) {
                throw new IllegalArgumentException("vertex stride must be 8");
            }
            return nativeRaceStep(handle, vertices, closed, vehicle, dt);
        }

        /** Each rival is x y z yaw speed s lateral id. At most 8 rivals. */
        public int setRivals(float[] rivals) {
            if (handle == 0) {
                throw new IllegalStateException("race closed");
            }
            if (rivals != null && rivals.length % 8 != 0) {
                throw new IllegalArgumentException("rival stride must be 8");
            }
            return nativeRaceSetRivals(handle, rivals);
        }

        /** Step from a packed .r6course descriptor produced by
         *  tools/engine/course_descriptor.py. The closed flag comes from the
         *  descriptor header. */
        public int step(byte[] descriptor, float[] vehicle, float dt) {
            if (handle == 0) {
                throw new IllegalStateException("race closed");
            }
            return nativeRaceStepDescriptor(handle, descriptor, vehicle, dt);
        }

        /** State indices: playState outcome elapsed countdown lap lapTime
         *  lastLap bestLap s progress odo lateral height halfWidth speed
         *  offroadTime wrongWayTime surface offroad checkpointFlags
         *  rivalGap rivalSide rivalPosition collisionCount. */
        public float[] state() {
            if (handle == 0) {
                throw new IllegalStateException("race closed");
            }
            return nativeRaceState(handle);
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
    private static native long nativeRaceCreate(int mode, int stage, int course, int area, float goalOdo, float timeLimit, float countdown, int laps, float wrongWayLimit, float offroadFactor);
    private static native void nativeRaceDestroy(long handle);
    private static native int nativeRaceSetRivals(long handle, float[] rivals);
    private static native int nativeRaceStep(long handle, float[] vertices, boolean closed, float[] vehicle, float dt);
    private static native int nativeRaceStepDescriptor(long handle, byte[] descriptor, float[] vehicle, float dt);
    private static native float[] nativeRaceState(long handle);

    static {
        System.loadLibrary("r6engine");
    }
}
