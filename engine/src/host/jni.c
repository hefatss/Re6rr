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
#include "r6/r6_car.h"
#include "r6/r6_course.h"
#include "r6/r6_custom.h"
#include "r6/r6_game.h"
#include "r6/r6_glsl.h"
#include "r6/r6_glsl_manifest.h"
#include "r6/r6_physics.h"
#include "r6/r6_race.h"
#include "r6/r6_story.h"

static r6_engine *from_handle(jlong handle) {
    return (r6_engine *)(size_t)handle;
}

/* Parse a packed descriptor from Java into caller-owned vertex storage. */
static int course_from_descriptor(JNIEnv *env, jbyteArray descriptor,
                                  uint32_t *flags,
                                  r6_course_vertex **out, size_t *count) {
    unsigned char *blob = NULL;
    jsize length;
    size_t needed = 0;
    jint rc;
    *out = NULL;
    *count = 0;
    if (!descriptor) {
        return R6_ERR_ARG;
    }
    length = (*env)->GetArrayLength(env, descriptor);
    blob = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!blob) {
        return R6_ERR_MEMORY;
    }
    (*env)->GetByteArrayRegion(env, descriptor, 0, length, (jbyte *)blob);
    if ((*env)->ExceptionCheck(env) ||
        r6_course_descriptor_parse(blob, (size_t)length, flags, NULL, 0,
                                   &needed) != R6_ERR_BUFFER || needed == 0) {
        free(blob);
        return R6_ERR_FORMAT;
    }
    *out = (r6_course_vertex *)malloc(needed * sizeof(**out));
    if (!*out) {
        free(blob);
        return R6_ERR_MEMORY;
    }
    rc = (jint)r6_course_descriptor_parse(blob, (size_t)length, flags, *out,
                                          needed, count);
    free(blob);
    if (rc != R6_OK) {
        free(*out);
        *out = NULL;
    }
    return rc;
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

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleSetSurface(JNIEnv *env, jclass cls,
                                                      jlong handle,
                                                      jint surface) {
    (void)env;
    (void)cls;
    if (!handle || surface < 0 || surface > 2) {
        return R6_ERR_ARG;
    }
    return (jint)r6_vehicle_set_surface((r6_vehicle *)(size_t)handle,
                                        (uint8_t)surface);
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

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeVehicleClampToCourseDescriptor(
        JNIEnv *env, jclass cls, jlong handle, jbyteArray descriptor) {
    r6_course_vertex *path = NULL;
    uint32_t flags = 0;
    size_t count = 0;
    jint rc;
    (void)cls;
    if (!handle) {
        return R6_ERR_ARG;
    }
    rc = course_from_descriptor(env, descriptor, &flags, &path, &count);
    if (rc != R6_OK) {
        return rc;
    }
    rc = (jint)r6_vehicle_clamp_to_course((r6_vehicle *)(size_t)handle,
                                          path, count, (flags & 1u) != 0);
    free(path);
    return rc;
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
Java_com_wmmt_re6rr_Re6Engine_nativeRaceSetRivals(JNIEnv *env, jclass cls,
                                                  jlong handle,
                                                  jfloatArray rivals) {
    r6_rival_state list[R6_RACE_MAX_RIVALS];
    jsize floats = 0;
    jsize count = 0;
    jfloat *data = NULL;
    jsize i;
    jint rc;
    (void)cls;
    if (!handle) {
        return R6_ERR_ARG;
    }
    if (rivals) {
        floats = (*env)->GetArrayLength(env, rivals);
        if (floats % 8 != 0) {
            return R6_ERR_ARG;
        }
        count = floats / 8;
        if (count > R6_RACE_MAX_RIVALS) {
            return R6_ERR_ARG;
        }
        data = (*env)->GetFloatArrayElements(env, rivals, NULL);
        if (!data) {
            return R6_ERR_MEMORY;
        }
        for (i = 0; i < count; i++) {
            const jfloat *p = data + (size_t)i * 8;
            list[i].x = p[0];
            list[i].y = p[1];
            list[i].z = p[2];
            list[i].yaw = p[3];
            list[i].speed = p[4];
            list[i].s = p[5];
            list[i].lateral = p[6];
            list[i].id = (uint32_t)p[7];
        }
        (*env)->ReleaseFloatArrayElements(env, rivals, data, JNI_ABORT);
    }
    rc = (jint)r6_race_set_rivals((r6_race *)(size_t)handle,
                                  rivals ? list : NULL, (size_t)count);
    return rc;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceSpawnRivals(JNIEnv *env, jclass cls,
                                                   jlong handle, jint count,
                                                   jfloat speed, jfloat spacing,
                                                   jfloat lateral) {
    (void)env;
    (void)cls;
    if (!handle || count < 0 || count > R6_RACE_MAX_RIVALS) {
        return R6_ERR_ARG;
    }
    return (jint)r6_race_spawn_rivals((r6_race *)(size_t)handle,
                                      (size_t)count, (float)speed,
                                      (float)spacing, (float)lateral);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeRaceStepDescriptor(
        JNIEnv *env, jclass cls, jlong handle, jbyteArray descriptor,
        jfloatArray vehicle, jfloat dt) {
    r6_course_vertex *path = NULL;
    r6_vehicle_state vstate;
    jfloat *vehicle_data = NULL;
    uint32_t flags = 0;
    size_t count = 0;
    jint rc;
    (void)cls;
    if (!handle || !descriptor || !vehicle) {
        return R6_ERR_ARG;
    }
    rc = course_from_descriptor(env, descriptor, &flags, &path, &count);
    if (rc != R6_OK) {
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
    result = (*env)->NewFloatArray(env, 27);
    if (result) {
        jfloat values[27] = {
            (jfloat)state.play_state, (jfloat)state.outcome,
            state.elapsed, state.countdown, (jfloat)state.lap,
            state.lap_time, state.last_lap, state.best_lap,
            state.s, state.progress, state.odo, state.lateral,
            state.height, state.half_width, state.speed,
            state.offroad_time, state.wrong_way_time,
            (jfloat)state.surface, (jfloat)state.offroad,
            (jfloat)state.checkpoint_flags,
            state.rival_gap, state.rival_side,
            (jfloat)state.rival_position, (jfloat)state.collision_count,
            (jfloat)state.checkpoint_count, (jfloat)state.checkpoint_next,
            (jfloat)state.checkpoint_mask
        };
        (*env)->SetFloatArrayRegion(env, result, 0, 27, values);
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

/* ---- P5 game flow ---------------------------------------------------- */

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameCreate(JNIEnv *env, jclass cls) {
    void *storage;
    r6_game *game;
    (void)env;
    (void)cls;
    storage = malloc(r6_game_size());
    if (!storage) {
        return 0;
    }
    game = r6_game_init(storage, r6_game_size(), NULL);
    if (!game) {
        free(storage);
        return 0;
    }
    return (jlong)(size_t)game;
}

JNIEXPORT void JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameDestroy(JNIEnv *env, jclass cls,
                                                jlong handle) {
    (void)env;
    (void)cls;
    free((void *)(size_t)handle);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGamePhase(JNIEnv *env, jclass cls,
                                              jlong handle) {
    (void)env;
    (void)cls;
    return (jint)r6_game_phase((const r6_game *)(size_t)handle);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameSelectCar(JNIEnv *env, jclass cls,
                                                  jlong handle, jint index) {
    (void)env;
    (void)cls;
    return (jint)r6_game_select_car((r6_game *)(size_t)handle, (int)index);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameSelectCourse(
        JNIEnv *env, jclass cls, jlong handle, jint course, jint area,
        jint stage) {
    (void)env;
    (void)cls;
    return (jint)r6_game_select_course((r6_game *)(size_t)handle, (int)course,
                                       (int)area, (int)stage);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameStart(JNIEnv *env, jclass cls,
                                              jlong handle) {
    (void)env;
    (void)cls;
    return (jint)r6_game_start((r6_game *)(size_t)handle);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameStep(JNIEnv *env, jclass cls,
                                             jlong handle, jint outcome,
                                             jfloat elapsed, jfloat dt) {
    r6_race_state state;
    unsigned char *bytes = (unsigned char *)&state;
    size_t i;
    (void)env;
    (void)cls;
    for (i = 0; i < sizeof(state); i++) {
        bytes[i] = 0;
    }
    state.outcome = (int)outcome;
    state.elapsed = (float)elapsed;
    return (jint)r6_game_step((r6_game *)(size_t)handle, (float)dt, &state);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameReset(JNIEnv *env, jclass cls,
                                              jlong handle) {
    (void)env;
    (void)cls;
    return (jint)r6_game_reset((r6_game *)(size_t)handle);
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameWriteConfig(JNIEnv *env, jclass cls,
                                                    jlong handle) {
    unsigned char blob[R6_ENMA_CFG_SIZE];
    jbyteArray result;
    (void)cls;
    if (r6_game_write_config((const r6_game *)(size_t)handle, blob,
                             sizeof(blob)) != R6_OK) {
        return NULL;
    }
    result = (*env)->NewByteArray(env, (jsize)sizeof(blob));
    if (result) {
        (*env)->SetByteArrayRegion(env, result, 0, (jsize)sizeof(blob),
                                   (jbyte *)blob);
    }
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeGameReadConfig(JNIEnv *env, jclass cls,
                                                   jlong handle,
                                                   jbyteArray blob) {
    unsigned char bytes[R6_ENMA_CFG_SIZE];
    jsize length;
    (void)cls;
    if (!blob) {
        return R6_ERR_ARG;
    }
    length = (*env)->GetArrayLength(env, blob);
    if (length < (jsize)sizeof(bytes)) {
        return R6_ERR_BUFFER;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, (jsize)sizeof(bytes),
                               (jbyte *)bytes);
    return (jint)r6_game_read_config((r6_game *)(size_t)handle, bytes,
                                     sizeof(bytes));
}

/* ---- Car catalog ----------------------------------------------------- */

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCarCatalogCount(JNIEnv *env, jclass cls,
                                                    jbyteArray blob) {
    jsize length;
    unsigned char *bytes;
    size_t count = 0;
    jint rc;
    (void)cls;
    if (!blob) {
        return 0;
    }
    length = (*env)->GetArrayLength(env, blob);
    bytes = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!bytes) {
        return 0;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, length, (jbyte *)bytes);
    rc = (jint)r6_car_catalog_parse(bytes, (size_t)length, NULL, 0, &count);
    free(bytes);
    return rc == R6_ERR_BUFFER ? (jint)count : 0;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCarCatalogModel(JNIEnv *env, jclass cls,
                                                    jbyteArray blob,
                                                    jint index) {
    r6_car_info *cars = NULL;
    unsigned char *bytes = NULL;
    jsize length;
    size_t count = 0;
    size_t needed = 0;
    jbyteArray result = NULL;
    (void)cls;
    if (!blob || index < 0) {
        return NULL;
    }
    length = (*env)->GetArrayLength(env, blob);
    bytes = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!bytes) {
        return NULL;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, length, (jbyte *)bytes);
    if (r6_car_catalog_parse(bytes, (size_t)length, NULL, 0, &needed) !=
        R6_ERR_BUFFER || (size_t)index >= needed) {
        free(bytes);
        return NULL;
    }
    cars = (r6_car_info *)malloc(needed * sizeof(*cars));
    if (!cars) {
        free(bytes);
        return NULL;
    }
    if (r6_car_catalog_parse(bytes, (size_t)length, cars, needed, &count) !=
        R6_OK) {
        free(cars);
        free(bytes);
        return NULL;
    }
    free(bytes);
    {
        size_t size = 0;
        while (size < R6_CAR_MODEL_SIZE && cars[index].model[size]) {
            size++;
        }
        result = (*env)->NewByteArray(env, (jsize)size);
        if (result && size) {
            (*env)->SetByteArrayRegion(env, result, 0, (jsize)size,
                                       (jbyte *)cars[index].model);
        }
    }
    free(cars);
    return result;
}

JNIEXPORT jfloatArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCarCatalogInfo(JNIEnv *env, jclass cls,
                                                   jbyteArray blob,
                                                   jint index) {
    r6_car_info *cars = NULL;
    unsigned char *bytes = NULL;
    jsize length;
    size_t needed = 0;
    size_t count = 0;
    jfloatArray result = NULL;
    (void)cls;
    if (!blob || index < 0) {
        return NULL;
    }
    length = (*env)->GetArrayLength(env, blob);
    bytes = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!bytes) {
        return NULL;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, length, (jbyte *)bytes);
    if (r6_car_catalog_parse(bytes, (size_t)length, NULL, 0, &needed) !=
        R6_ERR_BUFFER || (size_t)index >= needed) {
        free(bytes);
        return NULL;
    }
    cars = (r6_car_info *)malloc(needed * sizeof(*cars));
    if (!cars) {
        free(bytes);
        return NULL;
    }
    if (r6_car_catalog_parse(bytes, (size_t)length, cars, needed, &count) !=
        R6_OK) {
        free(cars);
        free(bytes);
        return NULL;
    }
    free(bytes);
    result = (*env)->NewFloatArray(env, 11);
    if (result) {
        const r6_car_info *car = &cars[index];
        jfloat values[11] = {
            (jfloat)car->model_id, (jfloat)car->visual_model_id,
            (jfloat)car->horsepower, (jfloat)car->engine_cc,
            (jfloat)car->drive, (jfloat)car->mission, (jfloat)car->flags,
            car->tire_front, car->tire_rear,
            car->tire_width_front, car->tire_width_rear
        };
        (*env)->SetFloatArrayRegion(env, result, 0, 11, values);
    }
    free(cars);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCarCatalogCharacterCount(JNIEnv *env,
                                                             jclass cls,
                                                             jbyteArray blob) {
    jsize length;
    unsigned char *bytes;
    jint result = -1;
    (void)cls;
    if (!blob) {
        return -1;
    }
    length = (*env)->GetArrayLength(env, blob);
    bytes = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!bytes) {
        return -1;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, length, (jbyte *)bytes);
    result = (jint)r6_car_catalog_character_count(bytes, (size_t)length);
    free(bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCarCatalogCharacterIndex(JNIEnv *env,
                                                             jclass cls,
                                                             jbyteArray blob,
                                                             jstring character) {
    jsize length;
    unsigned char *bytes;
    const char *name;
    jint result = -1;
    (void)cls;
    if (!blob || !character) {
        return -1;
    }
    length = (*env)->GetArrayLength(env, blob);
    bytes = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!bytes) {
        return -1;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, length, (jbyte *)bytes);
    name = (*env)->GetStringUTFChars(env, character, NULL);
    if (name) {
        result = (jint)r6_car_catalog_find_character(bytes, (size_t)length,
                                                     name);
        (*env)->ReleaseStringUTFChars(env, character, name);
    }
    free(bytes);
    return result;
}

/* Customization catalog: Java keeps the blob, this layer only validates it and
 * copies fixed-size records back to Java. */
static int custom_from_blob(JNIEnv *env, jbyteArray blob,
                            unsigned char **bytes, jsize *length,
                            r6_custom_catalog *catalog) {
    if (!blob) {
        return R6_ERR_ARG;
    }
    *length = (*env)->GetArrayLength(env, blob);
    *bytes = (unsigned char *)malloc((size_t)*length ? (size_t)*length : 1);
    if (!*bytes) {
        return R6_ERR_MEMORY;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, *length, (jbyte *)*bytes);
    if ((*env)->ExceptionCheck(env) ||
            r6_custom_catalog_parse(*bytes, (size_t)*length, catalog) !=
            R6_OK) {
        free(*bytes);
        *bytes = NULL;
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogCounts(JNIEnv *env,
                                                        jclass cls,
                                                        jbyteArray blob) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    jintArray result = NULL;
    jint values[5];
    jint rc = custom_from_blob(env, blob, &bytes, &length, &catalog);
    (void)cls;
    if (rc != R6_OK) {
        return NULL;
    }
    values[0] = (jint)catalog.color_count;
    values[1] = (jint)catalog.wheel_count;
    values[2] = (jint)catalog.aero_count;
    values[3] = (jint)catalog.tune_count;
    values[4] = (jint)catalog.tire_count;
    result = (*env)->NewIntArray(env, 5);
    if (result) {
        (*env)->SetIntArrayRegion(env, result, 0, 5, values);
    }
    free(bytes);
    return result;
}

static jbyteArray custom_name(JNIEnv *env, const char *text, size_t limit) {
    size_t length = 0;
    jbyteArray result;
    while (length < limit && text[length]) {
        length++;
    }
    result = (*env)->NewByteArray(env, (jsize)length);
    if (result && length) {
        (*env)->SetByteArrayRegion(env, result, 0, (jsize)length,
                                   (const jbyte *)text);
    }
    return result;
}

JNIEXPORT jfloatArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogColor(JNIEnv *env,
                                                      jclass cls,
                                                      jbyteArray blob,
                                                      jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    r6_custom_color color;
    jfloatArray result = NULL;
    jfloat values[19];
    size_t i;
    (void)cls;
    if (custom_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_custom_catalog_color(&catalog, (size_t)index, &color) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = (jfloat)color.id;
    values[1] = (jfloat)color.icon;
    values[2] = (jfloat)color.feel;
    for (i = 0; i < 4; i++) {
        values[3 + i] = color.body0[i];
        values[7 + i] = color.body1[i];
        values[11 + i] = color.spec[i];
        values[15 + i] = color.params[i];
    }
    result = (*env)->NewFloatArray(env, 19);
    if (result) {
        (*env)->SetFloatArrayRegion(env, result, 0, 19, values);
    }
    free(bytes);
    return result;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogColorName(
        JNIEnv *env, jclass cls, jbyteArray blob, jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    r6_custom_color color;
    jbyteArray result = NULL;
    (void)cls;
    if (custom_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_custom_catalog_color(&catalog, (size_t)index, &color) != R6_OK) {
        free(bytes);
        return NULL;
    }
    result = custom_name(env, color.name, sizeof(color.name));
    free(bytes);
    return result;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogName(
        JNIEnv *env, jclass cls, jbyteArray blob, jint section, jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    jbyteArray result = NULL;
    (void)cls;
    if (custom_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK) {
        return NULL;
    }
    if (section == 1) {
        r6_custom_wheel row;
        if (r6_custom_catalog_wheel(&catalog, (size_t)index, &row) == R6_OK) {
            result = custom_name(env, row.name, sizeof(row.name));
        }
    } else if (section == 2) {
        r6_custom_aero row;
        if (r6_custom_catalog_aero(&catalog, (size_t)index, &row) == R6_OK) {
            result = custom_name(env, row.name, sizeof(row.name));
        }
    } else if (section == 3) {
        r6_custom_tune row;
        if (r6_custom_catalog_tune(&catalog, (size_t)index, &row) == R6_OK) {
            result = custom_name(env, row.model, sizeof(row.model));
        }
    }
    free(bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogFlags(
        JNIEnv *env, jclass cls, jbyteArray blob, jint section, jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    jint result = -1;
    (void)cls;
    if (custom_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK) {
        return -1;
    }
    if (section == 1) {
        r6_custom_wheel row;
        if (r6_custom_catalog_wheel(&catalog, (size_t)index, &row) == R6_OK) {
            result = (jint)row.flags;
        }
    } else if (section == 2) {
        r6_custom_aero row;
        if (r6_custom_catalog_aero(&catalog, (size_t)index, &row) == R6_OK) {
            result = (jint)row.flags;
        }
    }
    free(bytes);
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogTune(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    r6_custom_tune tune;
    jintArray result = NULL;
    jint values[10 + R6_CUSTOM_DEFAULT_COLORS + R6_CUSTOM_CUSTOM_COLORS];
    size_t i;
    (void)cls;
    if (custom_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_custom_catalog_tune(&catalog, (size_t)index, &tune) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = tune.aero_category;
    values[1] = tune.limited_parts;
    values[2] = tune.pure_wheel_front;
    values[3] = tune.pure_wheel_rear;
    values[4] = tune.custom_wheel_front;
    values[5] = tune.custom_wheel_rear;
    values[6] = tune.change_tuning_disp;
    values[7] = tune.custom_gt_wing;
    values[8] = tune.wing_a_h;
    values[9] = tune.wing_n;
    for (i = 0; i < R6_CUSTOM_DEFAULT_COLORS; i++) {
        values[10 + i] = tune.default_color_ids[i];
    }
    for (i = 0; i < R6_CUSTOM_CUSTOM_COLORS; i++) {
        values[10 + R6_CUSTOM_DEFAULT_COLORS + i] =
            tune.custom_color_ids[i];
    }
    result = (*env)->NewIntArray(env, (jsize)(sizeof(values) / sizeof(values[0])));
    if (result) {
        (*env)->SetIntArrayRegion(env, result, 0,
                                  (jsize)(sizeof(values) / sizeof(values[0])),
                                  values);
    }
    free(bytes);
    return result;
}

JNIEXPORT jfloatArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeCustomCatalogTire(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_custom_catalog catalog;
    r6_custom_tire tire;
    jfloatArray result = NULL;
    jfloat values[3];
    (void)cls;
    if (custom_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_custom_catalog_tire(&catalog, (size_t)index, &tire) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = (jfloat)tire.kind;
    values[1] = (jfloat)tire.index;
    values[2] = tire.value;
    result = (*env)->NewFloatArray(env, 3);
    if (result) {
        (*env)->SetFloatArrayRegion(env, result, 0, 3, values);
    }
    free(bytes);
    return result;
}

/* Story catalog: Java owns the blob, this layer validates then copies. */
static int story_from_blob(JNIEnv *env, jbyteArray blob,
                           unsigned char **bytes, jsize *length,
                           r6_story_catalog *catalog) {
    if (!blob) {
        return R6_ERR_ARG;
    }
    *length = (*env)->GetArrayLength(env, blob);
    *bytes = (unsigned char *)malloc((size_t)*length ? (size_t)*length : 1);
    if (!*bytes) {
        return R6_ERR_MEMORY;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, *length, (jbyte *)*bytes);
    if ((*env)->ExceptionCheck(env) ||
            r6_story_catalog_parse(*bytes, (size_t)*length, catalog) != R6_OK) {
        free(*bytes);
        *bytes = NULL;
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static jintArray story_ints(JNIEnv *env, const jint *values, jsize count) {
    jintArray result = (*env)->NewIntArray(env, count);
    if (result) {
        (*env)->SetIntArrayRegion(env, result, 0, count, values);
    }
    return result;
}

static size_t story_cstr_length(const char *text) {
    size_t length = 0;
    while (text[length]) {
        length++;
    }
    return length;
}

static jbyteArray story_byte_array(JNIEnv *env, const char *text,
                                   size_t length) {
    jbyteArray result = (*env)->NewByteArray(env, (jsize)length);
    if (result && length) {
        (*env)->SetByteArrayRegion(env, result, 0, (jsize)length,
                                   (const jbyte *)text);
    }
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogCounts(JNIEnv *env, jclass cls,
                                                       jbyteArray blob) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    jint values[5];
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK) {
        return NULL;
    }
    values[0] = (jint)catalog.episode_count;
    values[1] = (jint)catalog.message_count;
    values[2] = (jint)catalog.event_count;
    values[3] = (jint)catalog.key_count;
    values[4] = (jint)catalog.string_count;
    free(bytes);
    return story_ints(env, values, 5);
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogEpisode(JNIEnv *env, jclass cls,
                                                       jbyteArray blob,
                                                       jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    r6_story_episode episode;
    jint values[12];
    size_t i;
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_story_catalog_episode(&catalog, (size_t)index, &episode) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = (jint)episode.enum_index;
    values[1] = (jint)episode.flags;
    values[2] = episode.message_count;
    values[3] = episode.event_count;
    for (i = 0; i < 4; i++) {
        values[4 + i] = episode.actors[i];
    }
    values[8] = episode.stage;
    values[9] = episode.stage_root;
    values[10] = episode.stage_day;
    values[11] = episode.cam_id;
    free(bytes);
    return story_ints(env, values, 12);
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogEpisodeName(
        JNIEnv *env, jclass cls, jbyteArray blob, jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    r6_story_episode episode;
    jbyteArray result = NULL;
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_story_catalog_episode(&catalog, (size_t)index, &episode) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    result = custom_name(env, episode.name, sizeof(episode.name));
    free(bytes);
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogMessage(JNIEnv *env, jclass cls,
                                                       jbyteArray blob,
                                                       jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    r6_story_message message;
    jint values[5];
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_story_catalog_message(&catalog, (size_t)index, &message) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = (jint)message.text_offset;
    values[1] = message.episode;
    values[2] = message.local_id;
    values[3] = message.text_len;
    values[4] = message.phase;
    free(bytes);
    return story_ints(env, values, 5);
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogEvent(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    r6_story_event event;
    jint values[11];
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_story_catalog_event(&catalog, (size_t)index, &event) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = event.episode;
    values[1] = event.phase;
    values[2] = event.kind;
    values[3] = event.start_frame;
    values[4] = event.end_frame;
    values[5] = (jint)event.range;
    values[6] = event.mes_id;
    values[7] = event.actor;
    values[8] = event.pos;
    values[9] = (jint)event.text_offset;
    values[10] = event.text_len;
    free(bytes);
    return story_ints(env, values, 11);
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogKey(JNIEnv *env, jclass cls,
                                                   jbyteArray blob, jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    r6_story_key key;
    jint values[4];
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK ||
            r6_story_catalog_key(&catalog, (size_t)index, &key) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = (jint)key.id_offset;
    values[1] = (jint)key.value_offset;
    values[2] = key.id_len;
    values[3] = key.value_len;
    free(bytes);
    return story_ints(env, values, 4);
}

/* Sections: 0 message text, 1 event label, 2 key ID, 3 key value. */
JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogText(JNIEnv *env, jclass cls,
                                                    jbyteArray blob,
                                                    jint section, jint index) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    char *text = NULL;
    jbyteArray result = NULL;
    jint rc;
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK) {
        return NULL;
    }
    text = (char *)malloc((size_t)length + 1);
    if (!text) {
        free(bytes);
        return NULL;
    }
    if (section == 0) {
        rc = r6_story_catalog_message_text(&catalog, (size_t)index, text,
                                           (size_t)length + 1);
    } else if (section == 1) {
        rc = r6_story_catalog_event_text(&catalog, (size_t)index, text,
                                         (size_t)length + 1);
    } else if (section == 2) {
        rc = r6_story_catalog_key_id(&catalog, (size_t)index, text,
                                     (size_t)length + 1);
    } else if (section == 3) {
        rc = r6_story_catalog_key_value(&catalog, (size_t)index, text,
                                        (size_t)length + 1);
    } else {
        rc = R6_ERR_ARG;
    }
    if (rc == R6_OK) {
        result = story_byte_array(env, text, story_cstr_length(text));
    }
    free(text);
    free(bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogFindEpisode(
        JNIEnv *env, jclass cls, jbyteArray blob, jstring name) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    const char *value;
    jint result = -1;
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK) {
        return -1;
    }
    value = name ? (*env)->GetStringUTFChars(env, name, NULL) : NULL;
    if (value) {
        result = (jint)r6_story_catalog_find_episode(&catalog, value);
        (*env)->ReleaseStringUTFChars(env, name, value);
    }
    free(bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Engine_nativeStoryCatalogFindKey(
        JNIEnv *env, jclass cls, jbyteArray blob, jstring key) {
    unsigned char *bytes = NULL;
    jsize length = 0;
    r6_story_catalog catalog;
    const char *value;
    jint result = -1;
    (void)cls;
    if (story_from_blob(env, blob, &bytes, &length, &catalog) != R6_OK) {
        return -1;
    }
    value = key ? (*env)->GetStringUTFChars(env, key, NULL) : NULL;
    if (value) {
        result = (jint)r6_story_catalog_find_key(&catalog, value);
        (*env)->ReleaseStringUTFChars(env, key, value);
    }
    free(bytes);
    return result;
}

/* GLSL binding manifest. Java owns the byte[]; the reader copies nothing and
 * all returned arrays are plain jints so no native pointers cross the bridge. */
static int glsl_from_blob(JNIEnv *env, jbyteArray blob, unsigned char **bytes,
                          r6_glsl_bindings_view *view) {
    jsize length;
    jint rc;
    *bytes = NULL;
    if (!blob) {
        return R6_ERR_ARG;
    }
    length = (*env)->GetArrayLength(env, blob);
    if ((*env)->ExceptionCheck(env)) {
        return R6_ERR_ARG;
    }
    *bytes = (unsigned char *)malloc((size_t)length ? (size_t)length : 1);
    if (!*bytes) {
        return R6_ERR_MEMORY;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, length, (jbyte *)*bytes);
    if ((*env)->ExceptionCheck(env)) {
        free(*bytes);
        *bytes = NULL;
        return R6_ERR_ARG;
    }
    rc = (jint)r6_glsl_bindings_init(view, *bytes, (size_t)length);
    if (rc != R6_OK) {
        free(*bytes);
        *bytes = NULL;
    }
    return rc;
}

static jintArray glsl_ints(JNIEnv *env, const jint *values, jsize count) {
    jintArray out = (*env)->NewIntArray(env, count);
    if (out) {
        (*env)->SetIntArrayRegion(env, out, 0, count, values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeCount(JNIEnv *env, jclass cls,
                                             jbyteArray data) {
    unsigned char *bytes;
    r6_glsl_bindings_view view;
    jint result;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) != R6_OK) {
        return -1;
    }
    result = (jint)view.count;
    free(bytes);
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeRecord(JNIEnv *env, jclass cls,
                                              jbyteArray data, jint index) {
    unsigned char *bytes;
    r6_glsl_bindings_view view;
    r6_glsl_bindings_record_info record;
    jint values[5];
    jintArray out = NULL;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) == R6_OK &&
        r6_glsl_bindings_get_record(&view, (uint32_t)index, &record) ==
        R6_OK) {
        values[0] = (jint)record.flags;
        values[1] = record.cbuffers;
        values[2] = record.samplers;
        values[3] = (jint)record.cbuffer_first;
        values[4] = (jint)record.name_off;
        out = glsl_ints(env, values, 5);
    }
    free(bytes);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeName(JNIEnv *env, jclass cls,
                                            jbyteArray data, jint offset) {
    unsigned char *bytes;
    r6_glsl_bindings_view view;
    const char *name;
    jstring out = NULL;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) == R6_OK) {
        name = r6_glsl_bindings_name(&view, (uint32_t)offset);
        if (name) {
            out = (*env)->NewStringUTF(env, name);
        }
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeCbuffer(JNIEnv *env, jclass cls,
                                               jbyteArray data, jint record,
                                               jint index) {
    unsigned char *bytes;
    r6_glsl_bindings_view view;
    r6_glsl_bindings_record_info info;
    r6_glsl_bindings_cbuffer_info block;
    jint values[7];
    jintArray out = NULL;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) == R6_OK &&
        r6_glsl_bindings_get_record(&view, (uint32_t)record, &info) == R6_OK &&
        r6_glsl_bindings_get_cbuffer(&view, &info, (uint32_t)index,
                                     &block) == R6_OK) {
        values[0] = (jint)block.binding;
        values[1] = (jint)block.name_off;
        values[2] = (jint)block.size;
        values[3] = block.slots;
        values[4] = block.ubo;
        values[5] = block.regions;
        values[6] = (jint)block.region_first;
        out = glsl_ints(env, values, 7);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeRegion(JNIEnv *env, jclass cls,
                                              jbyteArray data, jint record,
                                              jint cbuffer, jint index) {
    unsigned char *bytes;
    r6_glsl_bindings_view view;
    r6_glsl_bindings_record_info info;
    r6_glsl_bindings_cbuffer_info block;
    r6_glsl_manifest_region region;
    jint values[4];
    jintArray out = NULL;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) == R6_OK &&
        r6_glsl_bindings_get_record(&view, (uint32_t)record, &info) == R6_OK &&
        r6_glsl_bindings_get_cbuffer(&view, &info, (uint32_t)cbuffer,
                                     &block) == R6_OK &&
        r6_glsl_bindings_region(&view, &block, (uint32_t)index,
                                &region) == R6_OK) {
        values[0] = (jint)region.offset;
        values[1] = region.size;
        values[2] = region.kind;
        values[3] = region.type;
        out = glsl_ints(env, values, 4);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeSampler(JNIEnv *env, jclass cls,
                                               jbyteArray data, jint record,
                                               jint index) {
    unsigned char *bytes;
    r6_glsl_bindings_view view;
    r6_glsl_bindings_record_info info;
    r6_glsl_bindings_sampler_info sampler;
    jint values[3];
    jintArray out = NULL;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) == R6_OK &&
        r6_glsl_bindings_get_record(&view, (uint32_t)record, &info) == R6_OK &&
        r6_glsl_bindings_get_sampler(&view, &info, (uint32_t)index,
                                     &sampler) == R6_OK) {
        values[0] = (jint)sampler.unit;
        values[1] = (jint)sampler.texture_off;
        values[2] = (jint)sampler.sampler_off;
        out = glsl_ints(env, values, 3);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativeTextureUpload(
        JNIEnv *env, jclass cls, jint unit, jint format, jint width,
        jint height) {
    r6_glsl_texture_desc desc;
    jint values[6];
    (void)cls;
    if (r6_glsl_texture_upload((uint32_t)unit, (uint8_t)format,
                               (uint32_t)width, (uint32_t)height,
                               &desc) != R6_OK) {
        return NULL;
    }
    values[0] = (jint)desc.internal_format;
    values[1] = (jint)desc.format;
    values[2] = (jint)desc.type;
    values[3] = (jint)desc.width;
    values[4] = (jint)desc.height;
    values[5] = (jint)desc.size;
    return glsl_ints(env, values, 6);
}
