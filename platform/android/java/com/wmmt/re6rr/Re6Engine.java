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

        /** Surface from Race.state(): 0 road, 1 grass, 2 gravel. */
        public int setSurface(int surface) {
            if (handle == 0) {
                throw new IllegalStateException("vehicle closed");
            }
            return nativeVehicleSetSurface(handle, surface);
        }

        /** Clamp the car inside a packed .r6course descriptor. */
        public int clampToCourse(byte[] descriptor) {
            if (handle == 0) {
                throw new IllegalStateException("vehicle closed");
            }
            return nativeVehicleClampToCourseDescriptor(handle, descriptor);
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

        /** Spawn simple AI rivals on the current course. */
        public int spawnRivals(int count, float speed, float spacing,
                                float lateral) {
            if (handle == 0) {
                throw new IllegalStateException("race closed");
            }
            return nativeRaceSpawnRivals(handle, count, speed, spacing,
                                         lateral);
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
         *  rivalGap rivalSide rivalPosition collisionCount checkpointCount
         *  checkpointNext checkpointMask. */
        public float[] state() {
            if (handle == 0) {
                throw new IllegalStateException("race closed");
            }
            return nativeRaceState(handle);
        }
    }

    /** Game flow plus the recovered SConfigPlay byte layout. */
    public static class Game implements AutoCloseable {
        private long handle;

        private Game(long handle) {
            this.handle = handle;
        }

        @Override
        public void close() {
            if (handle != 0) {
                nativeGameDestroy(handle);
                handle = 0;
            }
        }

        public static Game create() {
            return new Game(nativeGameCreate());
        }

        public int phase() {
            return nativeGamePhase(handle);
        }

        public int selectCar(int index) {
            return nativeGameSelectCar(handle, index);
        }

        public int selectCourse(int course, int area, int stage) {
            return nativeGameSelectCourse(handle, course, area, stage);
        }

        public int start() {
            return nativeGameStart(handle);
        }

        /** outcome and elapsed come from Race.state() indices 1 and 2. */
        public int step(int outcome, float elapsed, float dt) {
            return nativeGameStep(handle, outcome, elapsed, dt);
        }

        public int reset() {
            return nativeGameReset(handle);
        }

        public byte[] writeConfig() {
            return nativeGameWriteConfig(handle);
        }

        public int readConfig(byte[] blob) {
            return nativeGameReadConfig(handle, blob);
        }
    }

    /** Wraps the packed .r6car catalog produced by
     *  tools/engine/car_catalog.py. */
    public static class CarCatalog {
        private static final java.nio.charset.Charset SHIFT_JIS =
                java.nio.charset.Charset.forName("Shift_JIS");
        private final byte[] blob;

        public CarCatalog(byte[] blob) {
            this.blob = blob;
        }

        public int count() {
            return nativeCarCatalogCount(blob);
        }

        /** Display name decoded from the cp932 field already in .r6car. */
        public String name(int index) {
            return text(index, 0);
        }

        /** Maker decoded from the cp932 field already in .r6car. */
        public String maker(int index) {
            return text(index, 1);
        }

        private String text(int index, int field) {
            byte[] raw = nativeCarCatalogText(blob, index, field);
            return raw == null ? null : SHIFT_JIS.decode(
                    java.nio.ByteBuffer.wrap(raw)).toString();
        }

        /** EngineSound for the native ENGMAP lookup, or -1 on old blobs or
         *  bad index. Available in .r6car version 3. */
        public int engineSound(int index) {
            return nativeCarCatalogEngineSound(blob, index);
        }

        /** Catalog index for a PLC_* model, or -1 when absent. */
        public int indexForModel(String model) {
            return nativeCarCatalogFindModel(blob, model);
        }

        /** Catalog index for a ModelID, or -1 when absent. */
        public int indexForId(int modelId) {
            return nativeCarCatalogFindId(blob, modelId);
        }

        /** Raw model code bytes, normally ASCII such as PLC_928GT. */
        public byte[] model(int index) {
            return nativeCarCatalogModel(blob, index);
        }

        /** modelId visualModelId horsepower engineCc drive mission flags
         *  tireFront tireRear tireWidthFront tireWidthRear. */
        public float[] info(int index) {
            return nativeCarCatalogInfo(blob, index);
        }

        /** Derived CRC_* -> PLC_* mappings packed in the catalog. */
        public int characterCount() {
            return nativeCarCatalogCharacterCount(blob);
        }

        /** Catalog car index for a character car, or -1 when unmapped. */
        public int carIndexForCharacter(String character) {
            return nativeCarCatalogCharacterIndex(blob, character);
        }

        /** Model bytes for a character car, or null when unmapped. */
        public byte[] modelForCharacter(String character) {
            int index = carIndexForCharacter(character);
            return index < 0 ? null : model(index);
        }
    }

    /** Wraps the packed .r6custom catalog produced by
     *  tools/engine/custom_catalog.py. */
    public static class CustomCatalog {
        private final byte[] blob;
        private final int[] counts;

        public CustomCatalog(byte[] blob) {
            this.blob = blob;
            this.counts = nativeCustomCatalogCounts(blob);
            if (counts == null || counts.length != 5) {
                throw new IllegalArgumentException("bad .r6custom blob");
            }
        }

        /** Section indexes: 0 colour, 1 wheel, 2 aero, 3 tune, 4 tire. */
        public int count(int section) {
            if (section < 0 || section >= counts.length) {
                throw new IllegalArgumentException("bad section");
            }
            return counts[section];
        }

        /** id icon feel body0[4] body1[4] spec[4] params[4]. */
        public float[] color(int index) {
            return nativeCustomCatalogColor(blob, index);
        }

        /** CP932 colour label decoded to Unicode. */
        public String colorName(int index) {
            byte[] raw = nativeCustomCatalogColorName(blob, index);
            return raw == null ? null :
                   new String(raw, java.nio.charset.Charset.forName("Shift_JIS"));
        }

        public String wheelName(int index) {
            return name(1, index);
        }

        public int wheelFlags(int index) {
            return flags(1, index);
        }

        public String aeroName(int index) {
            return name(2, index);
        }

        public int aeroFlags(int index) {
            return flags(2, index);
        }

        public String tuneModel(int index) {
            return name(3, index);
        }

        /** Index of the PLC_* tune record, or -1 when absent. */
        public int tuneIndexForModel(String model) {
            return nativeCustomCatalogFindTune(blob, model);
        }

        /** aeroCategory limitedParts pureFront pureRear customFront customRear
         *  changeTuningDisp customGTWing wingAH wingN, then 11 default and
         *  40 custom colour IDs. */
        public int[] tune(int index) {
            return nativeCustomCatalogTune(blob, index);
        }

        /** kind index value. */
        public float[] tire(int index) {
            return nativeCustomCatalogTire(blob, index);
        }

        private String name(int section, int index) {
            byte[] raw = nativeCustomCatalogName(blob, section, index);
            return raw == null ? null : new String(raw,
                   java.nio.charset.Charset.forName("US-ASCII"));
        }

        private int flags(int section, int index) {
            return nativeCustomCatalogFlags(blob, section, index);
        }
    }

    /** Wraps the packed .r6story catalog produced by
     *  tools/engine/story_catalog.py. */
    public static class StoryCatalog {
        private final byte[] blob;
        private final int[] counts;

        public StoryCatalog(byte[] blob) {
            this.blob = blob;
            this.counts = nativeStoryCatalogCounts(blob);
            if (counts == null || counts.length != 5) {
                throw new IllegalArgumentException("bad .r6story blob");
            }
        }

        /** Section indexes: 0 episode, 1 message, 2 event, 3 key, 4 string. */
        public int count(int section) {
            if (section < 0 || section >= counts.length) {
                throw new IllegalArgumentException("bad section");
            }
            return counts[section];
        }

        /** message phases[3], event phases[3], event kinds[4], branch B,
         *  ending, environment, enum-index zero and empty key values. */
        public int[] summary() {
            return nativeStoryCatalogSummary(blob);
        }

        /** enumIndex flags messageCount eventCount actor0..3 stage root day
         *  camera. Numeric actors and stage stay raw; no shipped mapping. */
        public int[] episode(int index) {
            return nativeStoryCatalogEpisode(blob, index);
        }

        public String episodeName(int index) {
            byte[] raw = nativeStoryCatalogEpisodeName(blob, index);
            return raw == null ? null : new String(raw,
                   java.nio.charset.StandardCharsets.US_ASCII);
        }

        /** textOffset episode localId textLen phase. */
        public int[] message(int index) {
            return nativeStoryCatalogMessage(blob, index);
        }

        /** episode phase kind start end range mesId actor pos textOffset len. */
        public int[] event(int index) {
            return nativeStoryCatalogEvent(blob, index);
        }

        /** idOffset valueOffset idLen valueLen. */
        public int[] key(int index) {
            return nativeStoryCatalogKey(blob, index);
        }

        public String messageText(int index) {
            return utf8(0, index);
        }

        public String eventText(int index) {
            return utf8(1, index);
        }

        public String keyId(int index) {
            return utf8(2, index);
        }

        public String keyValue(int index) {
            return utf8(3, index);
        }

        public String text(int section, int index) {
            return utf8(section, index);
        }

        public int findEpisode(String name) {
            return nativeStoryCatalogFindEpisode(blob, name);
        }

        public int findKey(String key) {
            return nativeStoryCatalogFindKey(blob, key);
        }

        private String utf8(int section, int index) {
            byte[] raw = nativeStoryCatalogText(blob, section, index);
            return raw == null ? null : new String(raw,
                   java.nio.charset.StandardCharsets.UTF_8);
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
    private static native int nativeVehicleSetSurface(long handle, int surface);
    private static native float[] nativeVehicleState(long handle);
    private static native int nativeVehicleClampToCourseDescriptor(long handle, byte[] descriptor);
    private static native long nativeRaceCreate(int mode, int stage, int course, int area, float goalOdo, float timeLimit, float countdown, int laps, float wrongWayLimit, float offroadFactor);
    private static native void nativeRaceDestroy(long handle);
    private static native int nativeRaceSetRivals(long handle, float[] rivals);
    private static native int nativeRaceSpawnRivals(long handle, int count, float speed, float spacing, float lateral);
    private static native int nativeRaceStep(long handle, float[] vertices, boolean closed, float[] vehicle, float dt);
    private static native int nativeRaceStepDescriptor(long handle, byte[] descriptor, float[] vehicle, float dt);
    private static native float[] nativeRaceState(long handle);
    private static native long nativeGameCreate();
    private static native void nativeGameDestroy(long handle);
    private static native int nativeGamePhase(long handle);
    private static native int nativeGameSelectCar(long handle, int index);
    private static native int nativeGameSelectCourse(long handle, int course, int area, int stage);
    private static native int nativeGameStart(long handle);
    private static native int nativeGameStep(long handle, int outcome, float elapsed, float dt);
    private static native int nativeGameReset(long handle);
    private static native byte[] nativeGameWriteConfig(long handle);
    private static native int nativeGameReadConfig(long handle, byte[] blob);
    private static native int nativeCarCatalogCount(byte[] blob);
    private static native int nativeCarCatalogEngineSound(byte[] blob,
                                                          int index);
    private static native int nativeCarCatalogFindModel(byte[] blob, String model);
    private static native int nativeCarCatalogFindId(byte[] blob, int modelId);
    private static native byte[] nativeCarCatalogText(byte[] blob, int index,
                                                       int field);
    private static native byte[] nativeCarCatalogModel(byte[] blob, int index);
    private static native float[] nativeCarCatalogInfo(byte[] blob, int index);
    private static native int nativeCarCatalogCharacterCount(byte[] blob);
    private static native int[] nativeCustomCatalogCounts(byte[] blob);
    private static native float[] nativeCustomCatalogColor(byte[] blob, int index);
    private static native byte[] nativeCustomCatalogColorName(byte[] blob, int index);
    private static native byte[] nativeCustomCatalogName(byte[] blob, int section, int index);
    private static native int nativeCustomCatalogFlags(byte[] blob, int section, int index);
    private static native int nativeCustomCatalogFindTune(byte[] blob, String model);
    private static native int[] nativeCustomCatalogTune(byte[] blob, int index);
    private static native float[] nativeCustomCatalogTire(byte[] blob, int index);
    private static native int[] nativeStoryCatalogCounts(byte[] blob);
    private static native int[] nativeStoryCatalogSummary(byte[] blob);
    private static native int[] nativeStoryCatalogEpisode(byte[] blob, int index);
    private static native byte[] nativeStoryCatalogEpisodeName(byte[] blob, int index);
    private static native int[] nativeStoryCatalogMessage(byte[] blob, int index);
    private static native int[] nativeStoryCatalogEvent(byte[] blob, int index);
    private static native int[] nativeStoryCatalogKey(byte[] blob, int index);
    private static native byte[] nativeStoryCatalogText(byte[] blob, int section, int index);
    private static native int nativeStoryCatalogFindEpisode(byte[] blob, String name);
    private static native int nativeStoryCatalogFindKey(byte[] blob, String key);
    private static native int nativeCarCatalogCharacterIndex(byte[] blob, String character);

    static {
        System.loadLibrary("r6engine");
    }
}
