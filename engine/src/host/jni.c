/* JNI bridge for Android. The Java side owns asset lookup (AssetManager or a
 * user-supplied dump directory) and gzip container reads; it passes plain
 * bytes to this layer. The engine core itself stays platform-independent.
 *
 * Java class: com.hefatss.re6rr.Re6Engine
 */
#include <jni.h>
#include <stdlib.h>

#include "r6/r6.h"
#include "r6/r6_asset.h"

static r6_engine *from_handle(jlong handle) {
    return (r6_engine *)(size_t)handle;
}

JNIEXPORT jlong JNICALL
Java_com_hefatss_re6rr_Re6Engine_nativeCreate(JNIEnv *env, jclass cls) {
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
Java_com_hefatss_re6rr_Re6Engine_nativeDestroy(JNIEnv *env, jclass cls,
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
Java_com_hefatss_re6rr_Re6Engine_nativeLoadScript(JNIEnv *env, jclass cls,
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
Java_com_hefatss_re6rr_Re6Engine_nativeLoadContext(JNIEnv *env, jclass cls,
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
Java_com_hefatss_re6rr_Re6Engine_nativeCallVec3(JNIEnv *env, jclass cls,
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
Java_com_hefatss_re6rr_Re6Engine_nativeCallNumber(JNIEnv *env, jclass cls,
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
Java_com_hefatss_re6rr_Re6Engine_nativeHasFunction(JNIEnv *env, jclass cls,
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
Java_com_hefatss_re6rr_Re6Engine_nativeLastError(JNIEnv *env, jclass cls,
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

JNIEXPORT jbyteArray JNICALL
Java_com_hefatss_re6rr_Re6Engine_nativeInflateGzip(JNIEnv *env, jclass cls,
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
