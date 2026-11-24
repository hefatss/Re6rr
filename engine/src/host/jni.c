/* JNI bridge for Android. The Java side owns asset lookup (AssetManager or a
 * user-supplied dump directory) and gzip container reads; it passes plain
 * bytes to this layer. The engine core itself stays platform-independent.
 *
 * Java class: com.wmmt.re6rr.Re6Engine
 */
#include <jni.h>
#include <stdlib.h>

#include "r6/r6.h"
#include "r6/r6_asset.h"
#include "r6/r6_course.h"
#include "r6/r6_physics.h"
#include "r6/r6_race.h"

static r6_engine *from_handle(jlong handle) {
    return (r6_engine *)(size_t)handle;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCreate(JNIEnv *env, jclass cls) {
    void *storage;
    r6_engine *engine;
    (void)env;
    (void)cls;
    storage = malloc(r6_engine_size());
    if (!storage) {
        return 0;
    }
    engine = r6_engine_init(storage, r6_engine_size(), NULL);
    if (!engine) {
        free(storage);
        return 0;
    }
    r6_engine_set_setting_const(engine);
    return (jlong)(size_t)engine;
}

JNIEXPORT void JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeDestroy(JNIEnv *env, jclass cls,
                                               jlong handle) {
    r6_engine *engine = from_handle(handle);
    void *storage = engine;
    (void)env;
    (void)cls;
    if (!engine) {
        return;
    }
    r6_engine_shutdown(engine);
    free(storage);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeLoadScript(JNIEnv *env, jclass cls,
                                                  jlong handle, jstring name,
                                                  jbyteArray bytes) {
    r6_engine *engine = from_handle(handle);
    const char *chunk = NULL;
    unsigned char *buffer = NULL;
    jsize length;
    int rc;
    (void)cls;
    if (!engine || !bytes) {
        return R6_ERR_ARG;
    }
    length = (*env)->GetArrayLength(env, bytes);
    if (length > 0) {
        buffer = (unsigned char *)malloc((size_t)length);
        if (!buffer) {
            return R6_ERR_MEMORY;
        }
        (*env)->GetByteArrayRegion(env, bytes, 0, length, (jbyte *)buffer);
        if ((*env)->ExceptionCheck(env)) {
            free(buffer);
            return R6_ERR_ARG;
        }
    }
    if (name) {
        chunk = (*env)->GetStringUTFChars(env, name, NULL);
    }
    rc = r6_engine_load_script(engine, chunk, buffer, (size_t)length);
    if (name && chunk) {
        (*env)->ReleaseStringUTFChars(env, name, chunk);
    }
    free(buffer);
    return (jint)rc;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeLoadContext(JNIEnv *env, jclass cls,
                                                   jlong handle,
                                                   jobjectArray names,
                                                   jobjectArray chunks) {
    r6_engine *engine = from_handle(handle);
    jsize count;
    r6_script_source *scripts = NULL;
    unsigned char **buffers = NULL;
    const char **utf = NULL;
    jsize i;
    int rc = R6_OK;
    (void)cls;
    if (!engine || !names || !chunks) {
        return R6_ERR_ARG;
    }
    count = (*env)->GetArrayLength(env, names);
    if (count != (*env)->GetArrayLength(env, chunks)) {
        return R6_ERR_ARG;
    }
    if (count > 0) {
        scripts = (r6_script_source *)calloc((size_t)count, sizeof(*scripts));
        buffers = (unsigned char **)calloc((size_t)count, sizeof(*buffers));
        utf = (const char **)calloc((size_t)count, sizeof(*utf));
        if (!scripts || !buffers || !utf) {
            rc = R6_ERR_MEMORY;
            goto cleanup;
        }
    }
    for (i = 0; i < count; i++) {
        jbyteArray bytes = (jbyteArray)(*env)->GetObjectArrayElement(env,
                                                                      chunks, i);
        jsize length;
        if (!bytes) {
            rc = R6_ERR_ARG;
            goto cleanup;
        }
        length = (*env)->GetArrayLength(env, bytes);
        buffers[i] = length ? (unsigned char *)malloc((size_t)length) : NULL;
        if (length && !buffers[i]) {
            (*env)->DeleteLocalRef(env, bytes);
            rc = R6_ERR_MEMORY;
            goto cleanup;
        }
        if (length) {
            (*env)->GetByteArrayRegion(env, bytes, 0, length,
                                       (jbyte *)buffers[i]);
        }
        (*env)->DeleteLocalRef(env, bytes);
        if ((*env)->ExceptionCheck(env)) {
            rc = R6_ERR_ARG;
            goto cleanup;
        }
        {
            jstring name = (jstring)(*env)->GetObjectArrayElement(env,
                                                                   names, i);
            if (name) {
                utf[i] = (*env)->GetStringUTFChars(env, name, NULL);
                (*env)->DeleteLocalRef(env, name);
            }
        }
        scripts[i].name = utf[i];
        scripts[i].data = buffers[i];
        scripts[i].size = (size_t)length;
    }
    rc = r6_engine_load_context(engine, scripts, (size_t)count);

cleanup:
    for (i = 0; i < count; i++) {
        if (utf[i] && scripts && scripts[i].name) {
            jstring holder = (jstring)(*env)->GetObjectArrayElement(env,
                                                                      names, i);
            if (holder) {
                (*env)->ReleaseStringUTFChars(env, holder, utf[i]);
                (*env)->DeleteLocalRef(env, holder);
            }
        }
        free(buffers ? buffers[i] : NULL);
    }
    free(utf);
    free(buffers);
    free(scripts);
    return (jint)rc;
}

JNIEXPORT jfloatArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCallVec3(JNIEnv *env, jclass cls,
                                                jlong handle, jstring name,
                                                jstring key, jint index) {
    r6_engine *engine = from_handle(handle);
    const char *function = NULL;
    const char *argument = NULL;
    float out[3];
    jfloatArray result = NULL;
    (void)cls;
    if (!engine || !name) {
        return NULL;
    }
    function = (*env)->GetStringUTFChars(env, name, NULL);
    if (key) {
        argument = (*env)->GetStringUTFChars(env, key, NULL);
    }
    if (r6_engine_call_vec3_key(engine, function, argument ? argument : "",
                                (int)index, out) == R6_OK) {
        result = (*env)->NewFloatArray(env, 3);
        if (result) {
            (*env)->SetFloatArrayRegion(env, result, 0, 3, out);
        }
    }
    if (argument) {
        (*env)->ReleaseStringUTFChars(env, key, argument);
    }
    if (function) {
        (*env)->ReleaseStringUTFChars(env, name, function);
    }
    return result;
}

JNIEXPORT jdouble JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCallNumber(JNIEnv *env, jclass cls,
                                                  jlong handle, jstring name) {
    r6_engine *engine = from_handle(handle);
    const char *function;
    double out = 0.0;
    (void)cls;
    if (!engine || !name) {
        return 0.0;
    }
    function = (*env)->GetStringUTFChars(env, name, NULL);
    r6_engine_call_number(engine, function, &out);
    (*env)->ReleaseStringUTFChars(env, name, function);
    return (jdouble)out;
}

JNIEXPORT jboolean JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeHasFunction(JNIEnv *env, jclass cls,
                                                   jlong handle, jstring name) {
    r6_engine *engine = from_handle(handle);
    const char *function;
    jboolean found = JNI_FALSE;
    (void)cls;
    if (!engine || !name) {
        return JNI_FALSE;
    }
    function = (*env)->GetStringUTFChars(env, name, NULL);
    found = r6_engine_has_function(engine, function) ? JNI_TRUE : JNI_FALSE;
    (*env)->ReleaseStringUTFChars(env, name, function);
    return found;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeLastError(JNIEnv *env, jclass cls,
                                                 jlong handle) {
    r6_engine *engine = from_handle(handle);
    char buffer[256];
    (void)cls;
    if (!engine || r6_engine_last_error(engine, buffer, sizeof(buffer)) !=
                       R6_OK) {
        buffer[0] = 0;
    }
    return (*env)->NewStringUTF(env, buffer);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleCreate(JNIEnv *env, jclass cls) {
    void *storage;
    r6_vehicle *vehicle;
    (void)env;
    (void)cls;
    storage = malloc(r6_vehicle_size());
    if (!storage) {
        return 0;
    }
    vehicle = r6_vehicle_init(storage, r6_vehicle_size(), NULL);
    return vehicle ? (jlong)(size_t)vehicle : 0;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleFromLua(JNIEnv *env, jclass cls,
                                                      jlong engine_handle,
                                                      jstring car,
                                                      jstring model) {
    r6_vehicle *vehicle;
    r6_vehicle_config config;
    const char *car_name = NULL;
    const char *model_name = NULL;
    void *storage;
    (void)cls;
    if (!engine_handle || !car) {
        return 0;
    }
    storage = malloc(r6_vehicle_size());
    if (!storage) {
        return 0;
    }
    car_name = (*env)->GetStringUTFChars(env, car, NULL);
    if (model) {
        model_name = (*env)->GetStringUTFChars(env, model, NULL);
    }
    if (r6_vehicle_config_from_lua((r6_engine *)(size_t)engine_handle,
                                   car_name, model_name, &config) != R6_OK) {
        vehicle = NULL;
    } else {
        vehicle = r6_vehicle_init(storage, r6_vehicle_size(), &config);
    }
    if (model_name) {
        (*env)->ReleaseStringUTFChars(env, model, model_name);
    }
    if (car_name) {
        (*env)->ReleaseStringUTFChars(env, car, car_name);
    }
    if (!vehicle) {
        free(storage);
        return 0;
    }
    return (jlong)(size_t)vehicle;
}

JNIEXPORT void JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleDestroy(JNIEnv *env, jclass cls,
                                                      jlong handle) {
    (void)env;
    (void)cls;
    free((void *)(size_t)handle);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleStep(JNIEnv *env, jclass cls,
                                                   jlong handle,
                                                   jfloat throttle,
                                                   jfloat brake, jfloat steer,
                                                   jint gear, jfloat dt) {
    (void)env;
    (void)cls;
    if (!handle) {
        return R6_ERR_ARG;
    }
    return (jint)r6_vehicle_step((r6_vehicle *)(size_t)handle, throttle,
                                 brake, steer, (int)gear, (float)dt);
}

JNIEXPORT jfloatArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleState(JNIEnv *env, jclass cls,
                                                    jlong handle) {
    r6_vehicle_state state;
    jfloatArray result = NULL;
    (void)cls;
    if (!handle ||
        r6_vehicle_get_state((r6_vehicle *)(size_t)handle, &state) != R6_OK) {
        return NULL;
    }
    result = (*env)->NewFloatArray(env, 15);
    if (result) {
        jfloat values[15] = {
            state.x, state.y, state.z, state.vx, state.vy,
            state.yaw, state.yaw_rate, state.speed, state.rpm,
            state.throttle, state.brake, state.steer,
            (jfloat)state.gear, state.odo, state.wheel_spin
        };
        (*env)->SetFloatArrayRegion(env, result, 0, 15, values);
    }
    return result;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceCreate(JNIEnv *env, jclass cls,
                                               jint mode, jint stage,
                                               jint course, jint area,
                                               jfloat goal_odo,
                                               jfloat time_limit,
                                               jfloat countdown, jint laps,
                                               jfloat wrong_way_limit,
                                               jfloat offroad_factor) {
    r6_race_config config;
    r6_race *race;
    void *storage;
    (void)env;
    (void)cls;
    r6_race_config_default(&config);
    config.mode = (int)mode;
    config.stage = (int)stage;
    config.course = (int)course;
    config.area = (int)area;
    config.goal_odo = (float)goal_odo;
    config.time_limit = (float)time_limit;
    config.countdown = (float)countdown;
    config.laps = (int)laps;
    config.wrong_way_limit = (float)wrong_way_limit;
    config.offroad_factor = (float)offroad_factor;
    storage = malloc(r6_race_size());
    if (!storage) {
        return 0;
    }
    race = r6_race_init(storage, r6_race_size(), &config);
    return race ? (jlong)(size_t)race : 0;
}

JNIEXPORT void JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceDestroy(JNIEnv *env, jclass cls,
                                                jlong handle) {
    (void)env;
    (void)cls;
    free((void *)(size_t)handle);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceStep(JNIEnv *env, jclass cls,
                                             jlong handle,
                                             jfloatArray vertices,
                                             jboolean closed,
                                             jfloatArray vehicle, jfloat dt) {
    r6_course_vertex *path = NULL;
    jfloat *path_data = NULL;
    jfloat *vehicle_data = NULL;
    r6_vehicle_state vstate;
    jsize path_floats = 0;
    jsize count = 0;
    jsize i;
    jint rc;
    (void)cls;
    if (!handle || !vehicle) {
        return R6_ERR_ARG;
    }
    if (vertices) {
        path_floats = (*env)->GetArrayLength(env, vertices);
        if (path_floats % 8 != 0) {
            return R6_ERR_ARG;
        }
        count = path_floats / 8;
    }
    if (count) {
        path = (r6_course_vertex *)malloc((size_t)count * sizeof(*path));
        if (!path) {
            return R6_ERR_MEMORY;
        }
        path_data = (*env)->GetFloatArrayElements(env, vertices, NULL);
        if (!path_data) {
            free(path);
            return R6_ERR_MEMORY;
        }
        for (i = 0; i < count; i++) {
            const jfloat *p = path_data + (size_t)i * 8;
            path[i].x = p[0];
            path[i].y = p[1];
            path[i].z = p[2];
            path[i].half_width = p[3];
            path[i].surface = (uint8_t)p[4];
            path[i].flags = (uint8_t)p[5];
            path[i].reserved = (uint16_t)p[6];
        }
    }
    vehicle_data = (*env)->GetFloatArrayElements(env, vehicle, NULL);
    if (!vehicle_data || (*env)->GetArrayLength(env, vehicle) < 15) {
        if (vehicle_data) {
            (*env)->ReleaseFloatArrayElements(env, vehicle, vehicle_data,
                                              JNI_ABORT);
        }
        if (path_data) {
            (*env)->ReleaseFloatArrayElements(env, vertices, path_data,
                                              JNI_ABORT);
        }
        free(path);
        return R6_ERR_ARG;
    }
    {
        unsigned char *bytes = (unsigned char *)&vstate;
        size_t byte_index;
        for (byte_index = 0; byte_index < sizeof(vstate); byte_index++) {
            bytes[byte_index] = 0;
        }
    }
    vstate.x = vehicle_data[0];
    vstate.y = vehicle_data[1];
    vstate.z = vehicle_data[2];
    vstate.vx = vehicle_data[3];
    vstate.vy = vehicle_data[4];
    vstate.yaw = vehicle_data[5];
    vstate.yaw_rate = vehicle_data[6];
    vstate.speed = vehicle_data[7];
    vstate.rpm = vehicle_data[8];
    vstate.throttle = vehicle_data[9];
    vstate.brake = vehicle_data[10];
    vstate.steer = vehicle_data[11];
    vstate.gear = (int)vehicle_data[12];
    vstate.odo = vehicle_data[13];
    vstate.wheel_spin = vehicle_data[14];
    rc = (jint)r6_race_step((r6_race *)(size_t)handle, path, (size_t)count,
                            closed == JNI_TRUE, &vstate, (float)dt);
    (*env)->ReleaseFloatArrayElements(env, vehicle, vehicle_data, JNI_ABORT);
    if (path_data) {
        (*env)->ReleaseFloatArrayElements(env, vertices, path_data, JNI_ABORT);
    }
    free(path);
    return rc;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceStepDescriptor(
        JNIEnv *env, jclass cls, jlong handle, jbyteArray descriptor,
        jfloatArray vehicle, jfloat dt) {
    r6_course_vertex *path = NULL;
    r6_vehicle_state vstate;
    jfloat *vehicle_data = NULL;
    unsigned char *blob = NULL;
    uint32_t flags = 0;
    size_t count = 0;
    jsize length;
    jint rc;
    (void)cls;
    if (!handle || !descriptor || !vehicle) {
        return R6_ERR_ARG;
    }
    length = (*env)->GetArrayLength(env, descriptor);
    blob = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!blob) {
        return R6_ERR_MEMORY;
    }
    (*env)->GetByteArrayRegion(env, descriptor, 0, length, (jbyte *)blob);
    if ((*env)->ExceptionCheck(env) ||
        r6_course_descriptor_parse(blob, (size_t)length, &flags, NULL, 0,
                                   &count) != R6_ERR_BUFFER || count == 0) {
        free(blob);
        return R6_ERR_FORMAT;
    }
    path = (r6_course_vertex *)malloc(count * sizeof(*path));
    if (!path) {
        free(blob);
        return R6_ERR_MEMORY;
    }
    rc = (jint)r6_course_descriptor_parse(blob, (size_t)length, &flags, path,
                                           count, &count);
    free(blob);
    if (rc != R6_OK) {
        free(path);
        return rc;
    }
    vehicle_data = (*env)->GetFloatArrayElements(env, vehicle, NULL);
    if (!vehicle_data || (*env)->GetArrayLength(env, vehicle) < 15) {
        if (vehicle_data) {
            (*env)->ReleaseFloatArrayElements(env, vehicle, vehicle_data,
                                              JNI_ABORT);
        }
        free(path);
        return R6_ERR_ARG;
    }
    {
        unsigned char *bytes = (unsigned char *)&vstate;
        size_t byte_index;
        for (byte_index = 0; byte_index < sizeof(vstate); byte_index++) {
            bytes[byte_index] = 0;
        }
    }
    vstate.x = vehicle_data[0];
    vstate.y = vehicle_data[1];
    vstate.z = vehicle_data[2];
    vstate.vx = vehicle_data[3];
    vstate.vy = vehicle_data[4];
    vstate.yaw = vehicle_data[5];
    vstate.yaw_rate = vehicle_data[6];
    vstate.speed = vehicle_data[7];
    vstate.rpm = vehicle_data[8];
    vstate.throttle = vehicle_data[9];
    vstate.brake = vehicle_data[10];
    vstate.steer = vehicle_data[11];
    vstate.gear = (int)vehicle_data[12];
    vstate.odo = vehicle_data[13];
    vstate.wheel_spin = vehicle_data[14];
    rc = (jint)r6_race_step((r6_race *)(size_t)handle, path, count,
                            (flags & 1u) != 0, &vstate, (float)dt);
    (*env)->ReleaseFloatArrayElements(env, vehicle, vehicle_data, JNI_ABORT);
    free(path);
    return rc;
}

JNIEXPORT jfloatArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceState(JNIEnv *env, jclass cls,
                                              jlong handle) {
    r6_race_state state;
    jfloatArray result;
    (void)cls;
    if (!handle ||
        r6_race_get_state((const r6_race *)(size_t)handle, &state) != R6_OK) {
        return NULL;
    }
    result = (*env)->NewFloatArray(env, 20);
    if (result) {
        jfloat values[20] = {
            (jfloat)state.play_state, (jfloat)state.outcome,
            state.elapsed, state.countdown, (jfloat)state.lap,
            state.lap_time, state.last_lap, state.best_lap,
            state.s, state.progress, state.odo, state.lateral,
            state.height, state.half_width, state.speed,
            state.offroad_time, state.wrong_way_time,
            (jfloat)state.surface, (jfloat)state.offroad,
            (jfloat)state.checkpoint_flags
        };
        (*env)->SetFloatArrayRegion(env, result, 0, 20, values);
    }
    return result;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeInflateGzip(JNIEnv *env, jclass cls,
                                                   jbyteArray bytes) {
    unsigned char *src = NULL;
    unsigned char *dst = NULL;
    jsize length;
    size_t expected = 0;
    size_t written = 0;
    jbyteArray result = NULL;
    (void)cls;
    if (!bytes) {
        return NULL;
    }
    length = (*env)->GetArrayLength(env, bytes);
    src = (unsigned char *)malloc((size_t)length);
    if (!src) {
        return NULL;
    }
    (*env)->GetByteArrayRegion(env, bytes, 0, length, (jbyte *)src);
    if ((*env)->ExceptionCheck(env) ||
        r6_gzip_expected_size(src, (size_t)length, &expected) != R6_OK) {
        free(src);
        return NULL;
    }
    dst = (unsigned char *)malloc(expected ? expected : 1);
    if (!dst) {
        free(src);
        return NULL;
    }
    if (r6_gzip_inflate(src, (size_t)length, dst, expected, &written) ==
        R6_OK) {
        result = (*env)->NewByteArray(env, (jsize)written);
        if (result) {
            (*env)->SetByteArrayRegion(env, result, 0, (jsize)written,
                                       (jbyte *)dst);
        }
    }
    free(dst);
    free(src);
    return result;
}
