/* JNI bridge for Android. The Java side owns asset lookup (AssetManager or a
 * user-supplied dump directory) and gzip container reads; it passes plain
 * bytes to this layer. The engine core itself stays platform-independent.
 *
 * Java class: com.wmmt.re6rr.Re6Engine
 */
#include <jni.h>
#include <stdlib.h>

/* Host-only libm declaration: the freestanding core never sees this file, and
 * Windows clang here has no CRT headers installed for the syntax check. */
extern double pow(double base, double exponent);

#include "r6/r6.h"
#include "r6/r6_asset.h"
#include "r6/r6_audio.h"
#include "r6/r6_bgm.h"
#include "r6/r6_car.h"
#include "r6/r6_config_3d.h"
#include "r6/r6_context.h"
#include "r6/r6_course.h"
#include "r6/r6_custom.h"
#include "r6/r6_emtis.h"
#include "r6/r6_enma_defaults.h"
#include "r6/r6_enma_exports.h"
#include "r6/r6_scene_env.h"
#include "r6/r6_enma_enums.h"
#include "r6/r6_engmap.h"
#include "r6/r6_game.h"
#include "r6/r6_honor_schema.h"
#include "r6/r6_lua_globals.h"
#include "r6/r6_lua_xrefs.h"
#include "r6/r6_lua_inventory.h"
#include "r6/r6_asset_inventory.h"
#include "r6/r6_pe_inventory.h"
#include "r6/r6_name_runs.h"
#include "r6/r6_lua_reg_tables.h"
#include "r6/r6_path_strings.h"
#include "r6/r6_enma_sim.h"
#include "r6/r6_ref_words.h"
#include "r6/r6_pdata_stats.h"
#include "r6/r6_nsh.h"
#include "r6/r6_stage_effect.h"
#include "r6/r6_engine_runtime.h"
#include "r6/r6_engine_sound.h"
#include "r6/r6_glsl.h"
#include "r6/r6_glsl_manifest.h"
#include "r6/r6_physics.h"
#include "r6/r6_race.h"
#include "r6/r6_story.h"
#include "r6/r6_vertex_layout.h"
#include "r6/r6_voice.h"

static r6_engine *from_handle(jlong handle) {
    return (r6_engine *)(size_t)handle;
}

static int raw_from_blob(JNIEnv *env, jbyteArray blob, unsigned char **bytes,
                         size_t *length);

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

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaGlobals_nativeHeader(JNIEnv *env, jclass cls,
                                            jbyteArray blob) {
    r6_lua_globals_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_globals_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.count;
    values[1] = (jlong)header.strings_off;
    values[2] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_LuaGlobals_nativeName(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index) {
    char name[R6_LUA_GLOBALS_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_globals_row(bytes, length, (uint32_t)index, name,
                           sizeof(name), NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaGlobals_nativeRow(JNIEnv *env, jclass cls,
                                         jbyteArray blob, jint index) {
    char name[R6_LUA_GLOBALS_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t calls = 0;
    uint32_t category = 0;
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_globals_row(bytes, length, (uint32_t)index, name,
                           sizeof(name), &calls, &category) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)calls;
    values[1] = (jlong)category;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaXrefs_nativeHeader(JNIEnv *env, jclass cls,
                                          jbyteArray blob) {
    r6_lua_xref_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_xref_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.count;
    values[1] = (jlong)header.strings_off;
    values[2] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_LuaXrefs_nativeName(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jint index) {
    char name[R6_LUA_XREF_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_xref_name(bytes, length, (uint32_t)index, name,
                         sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaXrefs_nativeRow(JNIEnv *env, jclass cls,
                                       jbyteArray blob, jint index) {
    r6_lua_xref_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_xref_row(bytes, length, (uint32_t)index, &row) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)row.via;
    values[1] = (jlong)row.func_count;
    values[2] = (jlong)row.table_count;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaXrefs_nativeFuncs(JNIEnv *env, jclass cls,
                                         jbyteArray blob, jint index) {
    r6_lua_xref_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t rva = 0;
    jlong *values = NULL;
    jlongArray out = NULL;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_xref_row(bytes, length, (uint32_t)index, &row) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values = (jlong *)malloc((row.func_count ? row.func_count : 1u) *
                             sizeof(jlong));
    if (values) {
        for (at = 0; at < row.func_count; at++) {
            if (r6_lua_xref_func(bytes, length, (uint32_t)index, at,
                                 &rva) != R6_OK) {
                free(values);
                values = NULL;
                break;
            }
            values[at] = (jlong)rva;
        }
    }
    free(bytes);
    if (!values) {
        return NULL;
    }
    out = (*env)->NewLongArray(env, (jsize)row.func_count);
    if (out && row.func_count) {
        (*env)->SetLongArrayRegion(env, out, 0, (jsize)row.func_count, values);
    }
    free(values);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaXrefs_nativeTables(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index) {
    r6_lua_xref_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t rva = 0;
    uint32_t kind = 0;
    uint32_t count = 0;
    jlong *values = NULL;
    jlongArray out = NULL;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_xref_row(bytes, length, (uint32_t)index, &row) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values = (jlong *)malloc((row.table_count * 3u + 1u) * sizeof(jlong));
    if (values) {
        for (at = 0; at < row.table_count; at++) {
            if (r6_lua_xref_table(bytes, length, (uint32_t)index, at,
                                  &rva, &kind, &count) != R6_OK) {
                free(values);
                values = NULL;
                break;
            }
            values[at * 3u] = (jlong)rva;
            values[at * 3u + 1u] = (jlong)kind;
            values[at * 3u + 2u] = (jlong)count;
        }
    }
    free(bytes);
    if (!values) {
        return NULL;
    }
    out = (*env)->NewLongArray(env, (jsize)(row.table_count * 3u));
    if (out && row.table_count) {
        (*env)->SetLongArrayRegion(env, out, 0,
                                   (jsize)(row.table_count * 3u), values);
    }
    free(values);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaXrefs_nativeUsers(JNIEnv *env, jclass cls,
                                         jbyteArray blob, jint index,
                                         jint table) {
    r6_lua_xref_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t count = 0;
    uint32_t rva = 0;
    jlong *values = NULL;
    jlongArray out = NULL;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_xref_row(bytes, length, (uint32_t)index, &row) != R6_OK ||
        r6_lua_xref_table(bytes, length, (uint32_t)index, (uint32_t)table,
                          NULL, NULL, &count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values = (jlong *)malloc((count ? count : 1u) * sizeof(jlong));
    if (values) {
        for (at = 0; at < count; at++) {
            if (r6_lua_xref_user(bytes, length, (uint32_t)index,
                                 (uint32_t)table, at, &rva) != R6_OK) {
                free(values);
                values = NULL;
                break;
            }
            values[at] = (jlong)rva;
        }
    }
    free(bytes);
    if (!values) {
        return NULL;
    }
    out = (*env)->NewLongArray(env, (jsize)count);
    if (out && count) {
        (*env)->SetLongArrayRegion(env, out, 0, (jsize)count, values);
    }
    free(values);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaEnums_nativeHeader(JNIEnv *env, jclass cls,
                                           jbyteArray blob) {
    r6_enma_enum_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_enum_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.count;
    values[1] = (jlong)header.strings_off;
    values[2] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaEnums_nativeName(JNIEnv *env, jclass cls,
                                         jbyteArray blob, jint index) {
    char name[R6_ENMA_ENUM_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_enum_name(bytes, length, (uint32_t)index, name,
                          sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_EnmaEnums_nativeCount(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t count = 0;
    jint out = -1;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_enum_count(bytes, length, (uint32_t)index, &count) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    out = (jint)count;
    return out;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_EnmaEnums_nativeValue(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index,
                                          jint ordinal) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t value = 0;
    char name[R6_ENMA_ENUM_NAME_CAP];
    jlong out = -1;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_enum_value(bytes, length, (uint32_t)index,
                           (uint32_t)ordinal, &value, name,
                           sizeof(name)) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    out = (jlong)value;
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaEnums_nativeSymbol(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint index,
                                           jint ordinal) {
    char name[R6_ENMA_ENUM_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_enum_value(bytes, length, (uint32_t)index,
                           (uint32_t)ordinal, NULL, name,
                           sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaEnums_nativeFind(JNIEnv *env, jclass cls,
                                         jbyteArray blob, jint index,
                                         jlong value) {
    char name[R6_ENMA_ENUM_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_enum_find(bytes, length, (uint32_t)index,
                          (uint32_t)value, name, sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaDefaults_nativeHeader(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    r6_enma_defaults_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[5];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_defaults_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.count;
    values[1] = (jlong)header.fields_off;
    values[2] = (jlong)header.data_off;
    values[3] = (jlong)header.strings_off;
    values[4] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 5);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 5, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaDefaults_nativeName(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint index) {
    char name[R6_ENMA_DEFAULT_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_defaults_struct(bytes, length, (uint32_t)index, name,
                                sizeof(name), NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaDefaults_nativeRow(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t written = 0;
    uint32_t count = 0;
    char name[R6_ENMA_DEFAULT_NAME_CAP];
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_defaults_struct(bytes, length, (uint32_t)index, name,
                                sizeof(name), &written, &count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)written;
    values[1] = (jlong)count;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaDefaults_nativeField(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jint index,
                                             jint field) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t offset = 0;
    uint32_t count = 0;
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_defaults_field(bytes, length, (uint32_t)index,
                               (uint32_t)field, &offset, &count, NULL,
                               0) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)offset;
    values[1] = (jlong)count;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_EnmaDefaults_nativeBytes(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jint index,
                                             jint field) {
    unsigned char buffer[0x400];
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t count = 0;
    jbyteArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_defaults_field(bytes, length, (uint32_t)index,
                               (uint32_t)field, NULL, &count, buffer,
                               sizeof(buffer)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewByteArray(env, (jsize)count);
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, (jsize)count,
                                   (const jbyte *)buffer);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaExports_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    r6_enma_exports_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_exports_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.count;
    values[1] = (jlong)header.strings_off;
    values[2] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaExports_nativeName(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint index) {
    char name[R6_ENMA_EXPORT_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_enma_exports_name(bytes, length, (uint32_t)index, name,
                             sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_EnmaExports_nativeFind(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jstring name) {
    const char *text = NULL;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t index = 0;
    jint out = -1;
    (void)cls;
    if (!name) {
        return -1;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        return -1;
    }
    if (raw_from_blob(env, blob, &bytes, &length) == R6_OK &&
        r6_enma_exports_find(bytes, length, text, &index) == R6_OK) {
        out = (jint)index;
    }
    free(bytes);
    (*env)->ReleaseStringUTFChars(env, name, text);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SceneEnvStats_nativeHeader(JNIEnv *env, jclass cls,
                                               jbyteArray blob) {
    r6_scene_env_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[13];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_scene_env_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.dirs;
    values[1] = (jlong)header.present;
    values[2] = (jlong)header.actor_slots;
    values[3] = (jlong)header.present_slots;
    values[4] = (jlong)header.nonzero;
    values[5] = (jlong)header.unique_actors;
    values[6] = (jlong)header.actor_min;
    values[7] = (jlong)header.actor_max;
    values[8] = (jlong)header.stages;
    values[9] = (jlong)header.unique_stages;
    values[10] = (jlong)header.stage_min;
    values[11] = (jlong)header.stage_max;
    values[12] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 13);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 13, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_SceneEnvStats_nativeName(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jint index) {
    char name[R6_SCENE_ENV_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_scene_env_name(bytes, length, (uint32_t)index, name,
                          sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SceneEnvStats_nativeRow(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint index) {
    r6_scene_env_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[9];
    jlongArray out = NULL;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_scene_env_row(bytes, length, (uint32_t)index, &row) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)row.present;
    values[1] = (jlong)row.stage;
    values[2] = (jlong)row.stage_root;
    values[3] = (jlong)row.stage_day;
    values[4] = (jlong)row.cam_id;
    for (at = 0; at < R6_SCENE_ENV_ACTORS; at++) {
        values[5 + at] = (jlong)row.actors[at];
    }
    out = (*env)->NewLongArray(env, 9);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 9, values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_SceneEnvStats_nativeFind(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jstring name) {
    const char *text = NULL;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t index = 0;
    jint out = -1;
    (void)cls;
    if (!name) {
        return -1;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        return -1;
    }
    if (raw_from_blob(env, blob, &bytes, &length) == R6_OK &&
        r6_scene_env_find(bytes, length, text, &index) == R6_OK) {
        out = (jint)index;
    }
    free(bytes);
    (*env)->ReleaseStringUTFChars(env, name, text);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaInventory_nativeHeader(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    r6_lua_inventory_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[15];
    jlongArray out = NULL;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_inventory_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.root_count;
    values[1] = (jlong)header.dir_count;
    values[2] = (jlong)header.strings_size;
    for (at = 0; at < R6_LUA_INVENTORY_ROOTS; at++) {
        values[3 + at * 6] = (jlong)header.files[at];
        values[4 + at * 6] = (jlong)header.bytes[at];
        values[5 + at * 6] = (jlong)header.defined[at];
        values[6 + at * 6] = (jlong)header.calls[at];
        values[7 + at * 6] = (jlong)header.undefined[at];
        values[8 + at * 6] = (jlong)header.native_candidates[at];
    }
    out = (*env)->NewLongArray(env, 15);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 15, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_LuaInventory_nativeName(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint index) {
    char name[R6_LUA_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_inventory_name(bytes, length, (uint32_t)index, name,
                              sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaInventory_nativeRow(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint index) {
    r6_lua_inventory_dir_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[4];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_lua_inventory_dir(bytes, length, (uint32_t)index, &row) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)row.root;
    values[1] = (jlong)row.files;
    values[2] = (jlong)row.bytes;
    values[3] = (jlong)row.with_logic;
    out = (*env)->NewLongArray(env, 4);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 4, values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_LuaInventory_nativeFind(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint root,
                                            jstring name) {
    const char *text = NULL;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t index = 0;
    jint out = -1;
    (void)cls;
    if (!name) {
        return -1;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        return -1;
    }
    if (raw_from_blob(env, blob, &bytes, &length) == R6_OK &&
        r6_lua_inventory_find(bytes, length, (uint32_t)root, text,
                              &index) == R6_OK) {
        out = (jint)index;
    }
    free(bytes);
    (*env)->ReleaseStringUTFChars(env, name, text);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeHeader(JNIEnv *env, jclass cls,
                                                jbyteArray blob) {
    r6_asset_inventory_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[11];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.root_count;
    values[1] = (jlong)header.classified[0];
    values[2] = (jlong)header.classified[1];
    values[3] = (jlong)header.ext_count[0];
    values[4] = (jlong)header.ext_count[1];
    values[5] = (jlong)header.magic_count[0];
    values[6] = (jlong)header.magic_count[1];
    values[7] = (jlong)header.folder_count[0];
    values[8] = (jlong)header.folder_count[1];
    values[9] = (jlong)header.shader_count;
    values[10] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 11);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 11, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeExt(JNIEnv *env, jclass cls,
                                              jbyteArray blob, jint index) {
    char name[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t root = 0;
    uint32_t files = 0;
    uint32_t lo = 0;
    uint32_t hi = 0;
    uint32_t kinds[R6_ASSET_INVENTORY_KINDS];
    jlong values[10];
    jlongArray out = NULL;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_ext(bytes, length, (uint32_t)index, name,
                               sizeof(name), &root, &files, &lo, &hi,
                               kinds) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)root;
    values[1] = (jlong)files;
    values[2] = ((jlong)lo | ((jlong)hi << 32));
    for (at = 0; at < R6_ASSET_INVENTORY_KINDS; at++) {
        values[3 + at] = (jlong)kinds[at];
    }
    out = (*env)->NewLongArray(env, 10);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 10, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeMagic(JNIEnv *env, jclass cls,
                                                jbyteArray blob, jint index) {
    char name[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t root = 0;
    uint32_t count = 0;
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_magic(bytes, length, (uint32_t)index, name,
                                 sizeof(name), &root, &count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)root;
    values[1] = (jlong)count;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeFolder(JNIEnv *env, jclass cls,
                                                 jbyteArray blob, jint index) {
    char name[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t root = 0;
    uint32_t files = 0;
    uint32_t lo = 0;
    uint32_t hi = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_folder(bytes, length, (uint32_t)index, name,
                                  sizeof(name), &root, &files, &lo,
                                  &hi) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)root;
    values[1] = (jlong)files;
    values[2] = ((jlong)lo | ((jlong)hi << 32));
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeShaderSize(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    char path[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t size = 0;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_shader(bytes, length, (uint32_t)index, path,
                                  sizeof(path), &size, NULL) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)size;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeExtName(JNIEnv *env, jclass cls,
                                                  jbyteArray blob,
                                                  jint index) {
    char name[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_ext(bytes, length, (uint32_t)index, name,
                               sizeof(name), NULL, NULL, NULL, NULL,
                               NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeMagicName(JNIEnv *env, jclass cls,
                                                    jbyteArray blob,
                                                    jint index) {
    char name[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_magic(bytes, length, (uint32_t)index, name,
                                 sizeof(name), NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeFolderName(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    char name[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_folder(bytes, length, (uint32_t)index, name,
                                  sizeof(name), NULL, NULL, NULL,
                                  NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeShaderPath(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    char path[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_shader(bytes, length, (uint32_t)index, path,
                                  sizeof(path), NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, path);
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_AssetInventory_nativeShaderHead(JNIEnv *env, jclass cls,
                                                     jbyteArray blob,
                                                     jint index) {
    char path[R6_ASSET_INVENTORY_NAME_CAP];
    unsigned char head[16];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jbyteArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_asset_inventory_shader(bytes, length, (uint32_t)index, path,
                                  sizeof(path), NULL, head) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewByteArray(env, 16);
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, 16, (const jbyte *)head);
    }
    return out;
}

static unsigned char *pe_copy_blob(JNIEnv *env, jbyteArray blob,
                                   size_t *length) {
    unsigned char *bytes = NULL;
    *length = 0;
    if (raw_from_blob(env, blob, &bytes, length) != R6_OK) {
        return NULL;
    }
    return bytes;
}

static jlongArray pe_new_longs(JNIEnv *env, const jlong *values, jsize count) {
    jlongArray out = (*env)->NewLongArray(env, count);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, count, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    r6_pe_inventory_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[28];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.file_size;
    values[2] = (jlong)header.machine;
    values[3] = (jlong)header.pe_magic;
    values[4] = (jlong)header.timestamp;
    values[5] = (jlong)header.image_base_lo;
    values[6] = (jlong)header.image_base_hi;
    values[7] = (jlong)header.entry_rva;
    values[8] = (jlong)header.size_of_image;
    values[9] = (jlong)header.directory_count;
    values[10] = (jlong)header.pdata_count;
    values[11] = (jlong)header.unique_unwind;
    values[12] = (jlong)header.code_bytes;
    values[13] = (jlong)header.text_bytes;
    values[14] = (jlong)header.leaf;
    values[15] = (jlong)header.chained;
    values[16] = (jlong)header.with_eh;
    values[17] = (jlong)header.reloc_blocks;
    values[18] = (jlong)header.reloc_entries;
    values[19] = (jlong)header.dll_count;
    values[20] = (jlong)header.import_count;
    values[21] = (jlong)header.export_count;
    values[22] = (jlong)header.tls_count;
    values[23] = (jlong)header.section_count;
    values[24] = (jlong)header.strings_size;
    values[25] = (jlong)header.guid_off;
    values[26] = (jlong)header.pdb_age;
    values[27] = (jlong)header.path_off;
    return pe_new_longs(env, values, 28);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeFunc(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint index) {
    uint32_t rva = 0;
    uint32_t end = 0;
    uint32_t length = 0;
    uint32_t leaf = 0;
    size_t blob_length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &blob_length);
    jlong values[4];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_func(bytes, blob_length, (uint32_t)index, &rva, &end,
                             &length, &leaf) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)rva;
    values[1] = (jlong)end;
    values[2] = (jlong)length;
    values[3] = (jlong)leaf;
    return pe_new_longs(env, values, 4);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeDllName(JNIEnv *env, jclass cls,
                                              jbyteArray blob, jint index) {
    char name[128];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_dll(bytes, length, (uint32_t)index, name,
                            sizeof(name), NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeDllRange(JNIEnv *env, jclass cls,
                                               jbyteArray blob, jint index) {
    char name[128];
    uint32_t first = 0;
    uint32_t count = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[2];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_dll(bytes, length, (uint32_t)index, name,
                            sizeof(name), &first, &count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)first;
    values[1] = (jlong)count;
    return pe_new_longs(env, values, 2);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeImp(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index) {
    char name[256];
    uint32_t kind = 0;
    uint32_t ordinal = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[2];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_import(bytes, length, (uint32_t)index, &kind,
                               &ordinal, name, sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)kind;
    values[1] = (jlong)ordinal;
    return pe_new_longs(env, values, 2);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeImportName(JNIEnv *env, jclass cls,
                                                 jbyteArray blob, jint index) {
    char name[256];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_import(bytes, length, (uint32_t)index, NULL, NULL,
                               name, sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeSectionName(JNIEnv *env, jclass cls,
                                                  jbyteArray blob,
                                                  jint index) {
    char name[128];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_section(bytes, length, (uint32_t)index, name,
                                sizeof(name), NULL, NULL, NULL, NULL,
                                NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeSection(JNIEnv *env, jclass cls,
                                              jbyteArray blob, jint index) {
    char name[128];
    uint32_t vsize = 0;
    uint32_t vaddr = 0;
    uint32_t raw_size = 0;
    uint32_t raw_ptr = 0;
    uint32_t characteristics = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[5];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_section(bytes, length, (uint32_t)index, name,
                                sizeof(name), &vsize, &vaddr, &raw_size,
                                &raw_ptr, &characteristics) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)vsize;
    values[1] = (jlong)vaddr;
    values[2] = (jlong)raw_size;
    values[3] = (jlong)raw_ptr;
    values[4] = (jlong)characteristics;
    return pe_new_longs(env, values, 5);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeExportName(JNIEnv *env, jclass cls,
                                                 jbyteArray blob, jint index) {
    char name[128];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_export(bytes, length, (uint32_t)index, name,
                               sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeTls(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index) {
    uint32_t lo = 0;
    uint32_t hi = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[2];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_tls(bytes, length, (uint32_t)index, &lo,
                            &hi) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)lo;
    values[1] = (jlong)hi;
    return pe_new_longs(env, values, 2);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PeInventory_nativePdbGuid(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    char guid[64];
    uint32_t age = 0;
    char path[512];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_pdb(bytes, length, guid, sizeof(guid), &age, path,
                            sizeof(path)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, guid);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_PeInventory_nativePdbAge(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    char guid[64];
    uint32_t age = 0;
    char path[512];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_pdb(bytes, length, guid, sizeof(guid), &age, path,
                            sizeof(path)) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)age;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PeInventory_nativePdbPath(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    char guid[64];
    uint32_t age = 0;
    char path[512];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_pdb(bytes, length, guid, sizeof(guid), &age, path,
                            sizeof(path)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, path);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_NameRuns_nativeHeader(JNIEnv *env, jclass cls,
                                          jbyteArray blob) {
    r6_name_runs_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[5];
    (void)cls;
    if (!bytes ||
        r6_name_runs_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.run_count;
    values[2] = (jlong)header.name_count;
    values[3] = (jlong)header.user_count;
    values[4] = (jlong)header.strings_size;
    return pe_new_longs(env, values, 5);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_NameRuns_nativeRun(JNIEnv *env, jclass cls,
                                       jbyteArray blob, jint index) {
    uint32_t rva = 0;
    uint32_t size = 0;
    uint32_t stride = 0;
    uint32_t count = 0;
    uint32_t name_first = 0;
    uint32_t user_first = 0;
    uint32_t user_count = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[7];
    (void)cls;
    if (!bytes ||
        r6_name_runs_run(bytes, length, (uint32_t)index, &rva, &size,
                         &stride, &count, &name_first, &user_first,
                         &user_count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)rva;
    values[1] = (jlong)size;
    values[2] = (jlong)stride;
    values[3] = (jlong)count;
    values[4] = (jlong)name_first;
    values[5] = (jlong)user_first;
    values[6] = (jlong)user_count;
    return pe_new_longs(env, values, 7);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_NameRuns_nativeName(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jint index) {
    char name[R6_NAME_RUNS_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_name_runs_name(bytes, length, (uint32_t)index, name,
                          sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_NameRuns_nativeRunName(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint run_index,
                                           jint local_index) {
    char name[R6_NAME_RUNS_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_name_runs_run_name(bytes, length, (uint32_t)run_index,
                              (uint32_t)local_index, name,
                              sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_NameRuns_nativeUser(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jint index) {
    uint32_t rva = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_name_runs_user(bytes, length, (uint32_t)index, &rva) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)rva;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_NameRuns_nativeFind(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jstring name) {
    uint32_t run = 0;
    uint32_t local = 0;
    uint32_t global = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    const char *text = NULL;
    jlong values[3];
    (void)cls;
    if (!bytes || !name) {
        free(bytes);
        return NULL;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        free(bytes);
        return NULL;
    }
    if (r6_name_runs_find(bytes, length, text, &run, &local,
                          &global) != R6_OK) {
        (*env)->ReleaseStringUTFChars(env, name, text);
        free(bytes);
        return NULL;
    }
    (*env)->ReleaseStringUTFChars(env, name, text);
    free(bytes);
    values[0] = (jlong)run;
    values[1] = (jlong)local;
    values[2] = (jlong)global;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeHeader(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    r6_lua_reg_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[5];
    (void)cls;
    if (!bytes ||
        r6_lua_reg_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.table_count;
    values[2] = (jlong)header.entry_count;
    values[3] = (jlong)header.user_count;
    values[4] = (jlong)header.strings_size;
    return pe_new_longs(env, values, 5);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeTable(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jint index) {
    uint32_t rva = 0;
    uint32_t size = 0;
    uint32_t stride = 0;
    uint32_t count = 0;
    uint32_t entry_first = 0;
    uint32_t user_first = 0;
    uint32_t user_count = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[7];
    (void)cls;
    if (!bytes ||
        r6_lua_reg_table(bytes, length, (uint32_t)index, &rva, &size,
                         &stride, &count, &entry_first, &user_first,
                         &user_count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)rva;
    values[1] = (jlong)size;
    values[2] = (jlong)stride;
    values[3] = (jlong)count;
    values[4] = (jlong)entry_first;
    values[5] = (jlong)user_first;
    values[6] = (jlong)user_count;
    return pe_new_longs(env, values, 7);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeEntryFunc(JNIEnv *env, jclass cls,
                                                 jbyteArray blob,
                                                 jint index) {
    char name[R6_LUA_REG_NAME_CAP];
    uint32_t func_rva = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_lua_reg_entry(bytes, length, (uint32_t)index, name,
                         sizeof(name), &func_rva) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)func_rva;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeEntryName(JNIEnv *env, jclass cls,
                                                 jbyteArray blob,
                                                 jint index) {
    char name[R6_LUA_REG_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_lua_reg_entry(bytes, length, (uint32_t)index, name,
                         sizeof(name), NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeTableEntryFunc(JNIEnv *env, jclass cls,
                                                      jbyteArray blob,
                                                      jint table_index,
                                                      jint local_index) {
    char name[R6_LUA_REG_NAME_CAP];
    uint32_t func_rva = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_lua_reg_table_entry(bytes, length, (uint32_t)table_index,
                               (uint32_t)local_index, name, sizeof(name),
                               &func_rva) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)func_rva;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeTableEntryName(JNIEnv *env, jclass cls,
                                                      jbyteArray blob,
                                                      jint table_index,
                                                      jint local_index) {
    char name[R6_LUA_REG_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_lua_reg_table_entry(bytes, length, (uint32_t)table_index,
                               (uint32_t)local_index, name, sizeof(name),
                               NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeUser(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint index) {
    uint32_t rva = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_lua_reg_user(bytes, length, (uint32_t)index, &rva) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)rva;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaRegTables_nativeFind(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jstring name) {
    uint32_t table = 0;
    uint32_t local = 0;
    uint32_t global = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    const char *text = NULL;
    jlong values[3];
    (void)cls;
    if (!bytes || !name) {
        free(bytes);
        return NULL;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        free(bytes);
        return NULL;
    }
    if (r6_lua_reg_find(bytes, length, text, &table, &local,
                        &global) != R6_OK) {
        (*env)->ReleaseStringUTFChars(env, name, text);
        free(bytes);
        return NULL;
    }
    (*env)->ReleaseStringUTFChars(env, name, text);
    free(bytes);
    values[0] = (jlong)table;
    values[1] = (jlong)local;
    values[2] = (jlong)global;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PathStrings_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    r6_path_strings_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[4];
    (void)cls;
    if (!bytes ||
        r6_path_strings_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.group_count;
    values[2] = (jlong)header.string_count;
    values[3] = (jlong)header.strings_size;
    return pe_new_longs(env, values, 4);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PathStrings_nativeGroup(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint index) {
    uint32_t kind = 0;
    uint32_t count = 0;
    uint32_t first = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[3];
    (void)cls;
    if (!bytes ||
        r6_path_strings_group(bytes, length, (uint32_t)index, &kind, &count,
                              &first) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)kind;
    values[1] = (jlong)count;
    values[2] = (jlong)first;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PathStrings_nativeGet(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jint index) {
    char text[R6_PATH_STRINGS_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_path_strings_get(bytes, length, (uint32_t)index, text,
                            sizeof(text)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, text);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PathStrings_nativeGroupGet(JNIEnv *env, jclass cls,
                                               jbyteArray blob,
                                               jint group_index,
                                               jint local_index) {
    char text[R6_PATH_STRINGS_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_path_strings_group_get(bytes, length, (uint32_t)group_index,
                                  (uint32_t)local_index, text,
                                  sizeof(text)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, text);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PathStrings_nativeFind(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jstring text) {
    uint32_t group = 0;
    uint32_t local = 0;
    uint32_t global = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    const char *needle = NULL;
    jlong values[3];
    (void)cls;
    if (!bytes || !text) {
        free(bytes);
        return NULL;
    }
    needle = (*env)->GetStringUTFChars(env, text, NULL);
    if (!needle) {
        free(bytes);
        return NULL;
    }
    if (r6_path_strings_find(bytes, length, needle, &group, &local,
                             &global) != R6_OK) {
        (*env)->ReleaseStringUTFChars(env, text, needle);
        free(bytes);
        return NULL;
    }
    (*env)->ReleaseStringUTFChars(env, text, needle);
    free(bytes);
    values[0] = (jlong)group;
    values[1] = (jlong)local;
    values[2] = (jlong)global;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaSimFacts_nativeHeader(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    r6_enma_sim_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[6];
    (void)cls;
    if (!bytes || r6_enma_sim_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.getter_count;
    values[2] = (jlong)header.hit_count;
    values[3] = (jlong)header.config_size;
    values[4] = (jlong)header.strings_size;
    values[5] = (jlong)header.strings_off;
    return pe_new_longs(env, values, 6);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaSimFacts_nativeGetter(JNIEnv *env, jclass cls,
                                              jbyteArray blob, jint index) {
    char name[R6_ENMA_SIM_NAME_CAP];
    char export_name[R6_ENMA_SIM_NAME_CAP];
    uint32_t first = 0;
    uint32_t count = 0;
    uint32_t kind = 0;
    uint32_t bits = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[4];
    (void)cls;
    if (!bytes ||
        r6_enma_sim_getter(bytes, length, (uint32_t)index, name,
                           sizeof(name), export_name, sizeof(export_name),
                           &first, &count, &kind, &bits) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)first;
    values[1] = (jlong)count;
    values[2] = (jlong)kind;
    values[3] = (jlong)bits;
    return pe_new_longs(env, values, 4);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaSimFacts_nativeGetterName(JNIEnv *env, jclass cls,
                                                  jbyteArray blob,
                                                  jint index) {
    char name[R6_ENMA_SIM_NAME_CAP];
    char export_name[R6_ENMA_SIM_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_enma_sim_getter(bytes, length, (uint32_t)index, name,
                           sizeof(name), export_name, sizeof(export_name),
                           NULL, NULL, NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, name);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_EnmaSimFacts_nativeGetterExport(JNIEnv *env, jclass cls,
                                                    jbyteArray blob,
                                                    jint index) {
    char name[R6_ENMA_SIM_NAME_CAP];
    char export_name[R6_ENMA_SIM_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_enma_sim_getter(bytes, length, (uint32_t)index, name,
                           sizeof(name), export_name, sizeof(export_name),
                           NULL, NULL, NULL, NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, export_name);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnmaSimFacts_nativeHit(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint index) {
    uint32_t offset = 0;
    uint32_t bits = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[2];
    (void)cls;
    if (!bytes ||
        r6_enma_sim_hit(bytes, length, (uint32_t)index, &offset,
                        &bits) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)offset;
    values[1] = (jlong)bits;
    return pe_new_longs(env, values, 2);
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_EnmaSimFacts_nativeConfig(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    unsigned char config[R6_ENMA_SIM_CONFIG_SIZE];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jbyteArray out = NULL;
    (void)cls;
    if (!bytes ||
        r6_enma_sim_config(bytes, length, config,
                           sizeof(config)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewByteArray(env, R6_ENMA_SIM_CONFIG_SIZE);
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, R6_ENMA_SIM_CONFIG_SIZE,
                                   (const jbyte *)config);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_RefWords_nativeHeader(JNIEnv *env, jclass cls,
                                          jbyteArray blob) {
    r6_ref_words_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[3];
    (void)cls;
    if (!bytes || r6_ref_words_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.word_count;
    values[2] = (jlong)header.xref_count;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_RefWords_nativeWord(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jint index) {
    uint32_t value = 0;
    uint32_t first = 0;
    uint32_t count = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[3];
    (void)cls;
    if (!bytes ||
        r6_ref_words_word(bytes, length, (uint32_t)index, &value, &first,
                          &count) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)value;
    values[1] = (jlong)first;
    values[2] = (jlong)count;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_RefWords_nativeXref(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jint index) {
    uint32_t rva = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_ref_words_xref(bytes, length, (uint32_t)index, &rva) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)rva;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_RefWords_nativeWordXref(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint word_index,
                                            jint local_index) {
    uint32_t rva = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_ref_words_word_xref(bytes, length, (uint32_t)word_index,
                               (uint32_t)local_index, &rva) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)rva;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_RefWords_nativeFind(JNIEnv *env, jclass cls,
                                        jbyteArray blob, jlong value) {
    uint32_t index = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_ref_words_find(bytes, length, (uint32_t)value, &index) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)index;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PdataStats_nativeHeader(JNIEnv *env, jclass cls,
                                            jbyteArray blob) {
    r6_pdata_stats_header header;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[14];
    (void)cls;
    if (!bytes || r6_pdata_stats_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.function_count;
    values[2] = (jlong)header.code_bytes;
    values[3] = (jlong)header.text_bytes;
    values[4] = (jlong)header.leaf;
    values[5] = (jlong)header.chained;
    values[6] = (jlong)header.with_eh;
    values[7] = (jlong)header.min_size;
    values[8] = (jlong)header.max_size;
    values[9] = (jlong)header.median;
    values[10] = (jlong)header.bucket_count;
    values[11] = (jlong)header.largest_count;
    values[12] = (jlong)header.strings_size;
    values[13] = (jlong)header.strings_off;
    return pe_new_longs(env, values, 14);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_PdataStats_nativeBucket(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint index) {
    char label[R6_PDATA_STATS_NAME_CAP];
    uint32_t count = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pdata_stats_bucket(bytes, length, (uint32_t)index, label,
                              sizeof(label), &count) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)count;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PdataStats_nativeBucketLabel(JNIEnv *env, jclass cls,
                                                 jbyteArray blob,
                                                 jint index) {
    char label[R6_PDATA_STATS_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pdata_stats_bucket(bytes, length, (uint32_t)index, label,
                              sizeof(label), NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, label);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PdataStats_nativeLargest(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jint index) {
    uint32_t begin = 0;
    uint32_t end = 0;
    uint32_t size = 0;
    uint32_t unwind = 0;
    uint32_t flags = 0;
    uint32_t leaf = 0;
    uint32_t chain_begin = 0;
    uint32_t chain_end = 0;
    uint32_t chain_unwind = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[9];
    (void)cls;
    if (!bytes ||
        r6_pdata_stats_largest(bytes, length, (uint32_t)index, &begin, &end,
                               &size, &unwind, &flags, &leaf, &chain_begin,
                               &chain_end, &chain_unwind, NULL, 0) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)begin;
    values[1] = (jlong)end;
    values[2] = (jlong)size;
    values[3] = (jlong)unwind;
    values[4] = (jlong)flags;
    values[5] = (jlong)leaf;
    values[6] = (jlong)chain_begin;
    values[7] = (jlong)chain_end;
    values[8] = (jlong)chain_unwind;
    return pe_new_longs(env, values, 9);
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_PdataStats_nativeLargestSection(JNIEnv *env, jclass cls,
                                                    jbyteArray blob,
                                                    jint index) {
    char section[R6_PDATA_STATS_NAME_CAP];
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pdata_stats_largest(bytes, length, (uint32_t)index, NULL, NULL,
                               NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                               section, sizeof(section)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    return (*env)->NewStringUTF(env, section);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_PdataStats_nativeFind(JNIEnv *env, jclass cls,
                                          jbyteArray blob, jlong begin) {
    uint32_t index = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    (void)cls;
    if (!bytes ||
        r6_pdata_stats_find(bytes, length, (uint32_t)begin, &index) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    return (jlong)index;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_PeInventory_nativeDirectory(JNIEnv *env, jclass cls,
                                                jbyteArray blob, jint index) {
    uint32_t dir_index = 0;
    uint32_t rva = 0;
    uint32_t size = 0;
    size_t length = 0;
    unsigned char *bytes = pe_copy_blob(env, blob, &length);
    jlong values[3];
    (void)cls;
    if (!bytes ||
        r6_pe_inventory_directory(bytes, length, (uint32_t)index, &dir_index,
                                  &rva, &size) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)dir_index;
    values[1] = (jlong)rva;
    values[2] = (jlong)size;
    return pe_new_longs(env, values, 3);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_HonorSchema_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    r6_honor_schema_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_honor_schema_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.type_count;
    values[1] = (jlong)header.strings_off;
    values[2] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_HonorSchema_nativeType(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint type) {
    char name[R6_HONOR_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_honor_schema_type(bytes, length, (uint32_t)type, name,
                             sizeof(name), NULL) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_HonorSchema_nativeFieldCount(JNIEnv *env, jclass cls,
                                                 jbyteArray blob, jint type) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    char name[R6_HONOR_NAME_CAP];
    uint32_t count = 0;
    jint out = -1;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_honor_schema_type(bytes, length, (uint32_t)type, name,
                             sizeof(name), &count) != R6_OK) {
        free(bytes);
        return -1;
    }
    free(bytes);
    out = (jint)count;
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_HonorSchema_nativeField(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jint type,
                                            jint field) {
    char name[R6_HONOR_NAME_CAP];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_honor_schema_field(bytes, length, (uint32_t)type,
                              (uint32_t)field, name, sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jobjectArray JNICALL
Java_com_wmmt_re6rr_ContextPaths_nativeList(JNIEnv *env, jclass cls,
                                            jstring car, jstring model) {
    const char *car_utf = NULL;
    const char *model_utf = NULL;
    char path[R6_CONTEXT_PATH_CAP];
    jobjectArray out = NULL;
    jclass string_class;
    jstring value;
    int set;
    int index;
    jsize at = 0;
    (void)cls;
    if (!car || !model) {
        return NULL;
    }
    car_utf = (*env)->GetStringUTFChars(env, car, NULL);
    model_utf = (*env)->GetStringUTFChars(env, model, NULL);
    string_class = car_utf && model_utf ?
        (*env)->FindClass(env, "java/lang/String") : NULL;
    if (string_class) {
        out = (*env)->NewObjectArray(env, R6_CONTEXT_PATH_COUNT,
                                     string_class, NULL);
    }
    if (out) {
        for (set = 0; set < R6_CONTEXT_SETS; set++) {
            for (index = 0; index < R6_CONTEXT_PATH_COUNT; index++) {
                if (r6_context_path(set, index, car_utf, model_utf, path,
                                    sizeof(path)) != R6_OK) {
                    continue;
                }
                value = (*env)->NewStringUTF(env, path);
                if (!value) {
                    out = NULL;
                    break;
                }
                (*env)->SetObjectArrayElement(env, out, at++, value);
                (*env)->DeleteLocalRef(env, value);
            }
            if (!out) {
                break;
            }
        }
        if (out && at != R6_CONTEXT_PATH_COUNT) {
            out = NULL;
        }
    }
    if (model_utf) {
        (*env)->ReleaseStringUTFChars(env, model, model_utf);
    }
    if (car_utf) {
        (*env)->ReleaseStringUTFChars(env, car, car_utf);
    }
    return out;
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

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_GlslBindings_nativePackUbo(JNIEnv *env, jclass cls,
                                               jbyteArray data, jint record,
                                               jint cbuffer,
                                               jdoubleArray values) {
    unsigned char *bytes = NULL;
    r6_glsl_bindings_view view;
    r6_glsl_bindings_record_info info;
    r6_glsl_bindings_cbuffer_info block;
    r6_glsl_region *regions = NULL;
    r6_glsl_value *packed = NULL;
    unsigned char *ubo = NULL;
    double *source = NULL;
    jsize source_count = 0;
    jsize cursor = 0;
    size_t written = 0;
    uint32_t index;
    jbyteArray out = NULL;
    (void)cls;
    if (glsl_from_blob(env, data, &bytes, &view) != R6_OK ||
        r6_glsl_bindings_get_record(&view, (uint32_t)record, &info) != R6_OK ||
        r6_glsl_bindings_get_cbuffer(&view, &info, (uint32_t)cbuffer,
                                     &block) != R6_OK) {
        goto done;
    }
    regions = (r6_glsl_region *)malloc(block.regions * sizeof(*regions));
    packed = (r6_glsl_value *)malloc(block.regions * sizeof(*packed));
    ubo = (unsigned char *)malloc(block.size ? block.size : 1);
    if (!regions || !packed || !ubo) {
        goto done;
    }
    if (values) {
        source_count = (*env)->GetArrayLength(env, values);
        if ((*env)->ExceptionCheck(env)) {
            goto done;
        }
        source = (double *)malloc((size_t)source_count * sizeof(*source));
        if (!source) {
            goto done;
        }
        (*env)->GetDoubleArrayRegion(env, values, 0, source_count, source);
        if ((*env)->ExceptionCheck(env)) {
            goto done;
        }
    }
    for (index = 0; index < block.regions; index++) {
        r6_glsl_manifest_region region;
        uint32_t part;
        uint32_t components;
        if (r6_glsl_bindings_region(&view, &block, index, &region) != R6_OK) {
            goto done;
        }
        regions[index].offset = region.offset;
        regions[index].size = region.size;
        regions[index].kind = region.kind;
        regions[index].type = region.type;
        packed[index].u = 0;
        components = region.kind == R6_GLSL_MATRIX ? 16u :
                     (region.kind == R6_GLSL_VECTOR ? 4u : 1u);
        for (part = 0; part < components && cursor < source_count; part++) {
            double value = source[cursor++];
            if (region.kind == R6_GLSL_SCALAR) {
                if (region.type == R6_GLSL_UINT) {
                    packed[index].u = (uint32_t)(int64_t)value;
                } else {
                    packed[index].f = (float)value;
                }
            } else {
                packed[index].m[part] = (float)value;
            }
        }
    }
    if (r6_glsl_pack_ubo(ubo, block.size, regions, packed, block.regions,
                         &written) == R6_OK) {
        out = (*env)->NewByteArray(env, (jsize)written);
        if (out) {
            (*env)->SetByteArrayRegion(env, out, 0, (jsize)written,
                                       (jbyte *)ubo);
        }
    }
done:
    free(source);
    free(ubo);
    free(packed);
    free(regions);
    free(bytes);
    return out;
}

/* Texture bridge. The core parses NTWD/NTLX headers and decodes RGBA8; Java
 * owns the compressed container bytes and the returned pixel array. */
static int raw_from_blob(JNIEnv *env, jbyteArray blob, unsigned char **bytes,
                         size_t *length) {
    jsize size;
    *bytes = NULL;
    *length = 0;
    if (!blob) {
        return R6_ERR_ARG;
    }
    size = (*env)->GetArrayLength(env, blob);
    if ((*env)->ExceptionCheck(env)) {
        return R6_ERR_ARG;
    }
    *bytes = (unsigned char *)malloc((size_t)size ? (size_t)size : 1);
    if (!*bytes) {
        return R6_ERR_MEMORY;
    }
    (*env)->GetByteArrayRegion(env, blob, 0, size, (jbyte *)*bytes);
    if ((*env)->ExceptionCheck(env)) {
        free(*bytes);
        *bytes = NULL;
        return R6_ERR_ARG;
    }
    *length = (size_t)size;
    return R6_OK;
}

static int nut_from_blob(JNIEnv *env, jbyteArray blob, unsigned char **bytes,
                         size_t *length, r6_ntwd_texture **textures,
                         uint16_t *count) {
    unsigned char *raw = NULL;
    size_t size = 0;
    r6_ntwd_header header;
    r6_ntwd_texture *items = NULL;
    if (raw_from_blob(env, blob, &raw, &size) != R6_OK) {
        return R6_ERR_ARG;
    }
    if (r6_ntwd_parse(raw, size, &header, NULL, 0) != R6_ERR_BUFFER ||
        header.texture_count == 0) {
        free(raw);
        return R6_ERR_FORMAT;
    }
    items = (r6_ntwd_texture *)malloc(
        (size_t)header.texture_count * sizeof(*items));
    if (!items) {
        free(raw);
        return R6_ERR_MEMORY;
    }
    if (r6_ntwd_parse(raw, size, &header, items,
                      header.texture_count) != R6_OK) {
        free(items);
        free(raw);
        return R6_ERR_FORMAT;
    }
    *bytes = raw;
    *length = size;
    *textures = items;
    *count = header.texture_count;
    return R6_OK;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_Re6Texture_nativeCount(JNIEnv *env, jclass cls,
                                            jbyteArray data) {
    unsigned char *bytes;
    size_t length;
    r6_ntwd_texture *textures;
    uint16_t count;
    jint result;
    (void)cls;
    if (nut_from_blob(env, data, &bytes, &length, &textures, &count) !=
        R6_OK) {
        return -1;
    }
    result = (jint)count;
    free(textures);
    free(bytes);
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Texture_nativeInfo(JNIEnv *env, jclass cls,
                                           jbyteArray data, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_ntwd_texture *textures = NULL;
    uint16_t count = 0;
    jint values[6];
    jintArray out = NULL;
    (void)cls;
    if (nut_from_blob(env, data, &bytes, &length, &textures, &count) !=
        R6_OK || (uint32_t)index >= count) {
        goto done;
    }
    values[0] = textures[index].width;
    values[1] = textures[index].height;
    values[2] = textures[index].format;
    values[3] = textures[index].faces;
    values[4] = (jint)textures[index].flags;
    values[5] = (jint)textures[index].data_size;
    out = glsl_ints(env, values, 6);
done:
    free(textures);
    free(bytes);
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Texture_nativeDecodeRgba(JNIEnv *env, jclass cls,
                                                 jbyteArray data, jint index,
                                                 jint level, jint face) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_ntwd_texture *textures = NULL;
    uint16_t count = 0;
    size_t needed = 0;
    unsigned char *pixels = NULL;
    jbyteArray out = NULL;
    (void)cls;
    if (nut_from_blob(env, data, &bytes, &length, &textures, &count) !=
        R6_OK || (uint32_t)index >= count) {
        goto done;
    }
    if (r6_nut_decode_rgba(bytes, length, &textures[index], (uint32_t)level,
                           (uint32_t)face, NULL, 0, &needed) !=
        R6_ERR_BUFFER || needed == 0) {
        goto done;
    }
    pixels = (unsigned char *)malloc(needed);
    if (!pixels) {
        goto done;
    }
    if (r6_nut_decode_rgba(bytes, length, &textures[index], (uint32_t)level,
                           (uint32_t)face, pixels, needed, &needed) == R6_OK) {
        out = (*env)->NewByteArray(env, (jsize)needed);
        if (out) {
            (*env)->SetByteArrayRegion(env, out, 0, (jsize)needed,
                                       (jbyte *)pixels);
        }
    }
done:
    free(pixels);
    free(textures);
    free(bytes);
    return out;
}

/* Audio bridge. Java owns the .nub bytes and receives only plain values; the
 * core parses the bank and points PCM views into the caller-owned blob. */
static int audio_from_blob(JNIEnv *env, jbyteArray blob, unsigned char **bytes,
                           size_t *length, r6_nub_header *header,
                           r6_nub_tone **tones, uint32_t *count) {
    unsigned char *raw = NULL;
    size_t size = 0;
    r6_nub_tone *items = NULL;
    if (raw_from_blob(env, blob, &raw, &size) != R6_OK) {
        return R6_ERR_ARG;
    }
    if (r6_nub_parse(raw, size, header, NULL, 0) != R6_ERR_BUFFER ||
        header->tone_count == 0) {
        free(raw);
        return R6_ERR_FORMAT;
    }
    items = (r6_nub_tone *)malloc((size_t)header->tone_count * sizeof(*items));
    if (!items) {
        free(raw);
        return R6_ERR_MEMORY;
    }
    if (r6_nub_parse(raw, size, header, items, header->tone_count) != R6_OK) {
        free(items);
        free(raw);
        return R6_ERR_FORMAT;
    }
    *bytes = raw;
    *length = size;
    *tones = items;
    *count = header->tone_count;
    return R6_OK;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Audio_nativeHeader(JNIEnv *env, jclass cls,
                                          jbyteArray data) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_nub_header header;
    r6_nub_tone *tones = NULL;
    uint32_t count = 0;
    jint values[5];
    jintArray out = NULL;
    (void)cls;
    if (audio_from_blob(env, data, &bytes, &length, &header, &tones,
                        &count) == R6_OK) {
        values[0] = (jint)header.bank_id;
        values[1] = (jint)header.tone_count;
        values[2] = (jint)header.header_size;
        values[3] = (jint)header.data_size;
        values[4] = (jint)header.first_record;
        out = glsl_ints(env, values, 5);
    }
    free(tones);
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Re6Audio_nativeTone(JNIEnv *env, jclass cls,
                                        jbyteArray data, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_nub_header header;
    r6_nub_tone *tones = NULL;
    uint32_t count = 0;
    jint values[17];
    jintArray out = NULL;
    (void)cls;
    if (audio_from_blob(env, data, &bytes, &length, &header, &tones,
                        &count) == R6_OK && (uint32_t)index < count) {
        const r6_nub_tone *tone = &tones[index];
        values[0] = (jint)tone->index;
        values[1] = (jint)tone->slot;
        values[2] = (jint)tone->group;
        values[3] = (jint)tone->record_offset;
        values[4] = (jint)tone->length;
        values[5] = (jint)tone->data_offset;
        values[6] = (jint)tone->flags;
        values[7] = (jint)tone->format_count;
        values[8] = (jint)tone->rate;
        values[9] = (jint)tone->channels;
        values[10] = (jint)tone->bits;
        values[11] = (jint)tone->loop_flag;
        values[12] = (jint)tone->three_d_param_no;
        values[13] = tone->format_tag;
        values[14] = tone->format_channels;
        values[15] = tone->block_align;
        values[16] = (jint)tone->byte_rate;
        out = glsl_ints(env, values, 17);
    }
    free(tones);
    free(bytes);
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_Re6Audio_nativeControl(JNIEnv *env, jclass cls,
                                           jbyteArray data, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_nub_header header;
    r6_nub_tone *tones = NULL;
    uint32_t count = 0;
    r6_nub_control control;
    jdouble values[8];
    jdoubleArray out = NULL;
    (void)cls;
    if (audio_from_blob(env, data, &bytes, &length, &header, &tones,
                        &count) == R6_OK && (uint32_t)index < count &&
        r6_nub_tone_control(bytes, length, &tones[index], &control) == R6_OK) {
        values[0] = tones[index].volume;
        values[1] = control.three_d_float_a;
        values[2] = control.three_d_float_b;
        values[3] = control.three_d_param_no;
        values[4] = control.volume_cap;
        values[5] = control.pan_cap;
        values[6] = control.bus_id;
        values[7] = control.voice_bus;
        out = (*env)->NewDoubleArray(env, 8);
        if (out) {
            (*env)->SetDoubleArrayRegion(env, out, 0, 8, values);
        }
    }
    free(tones);
    free(bytes);
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_Re6Audio_nativePcm(JNIEnv *env, jclass cls,
                                       jbyteArray data, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_nub_header header;
    r6_nub_tone *tones = NULL;
    uint32_t count = 0;
    const void *pcm = NULL;
    size_t size = 0;
    jbyteArray out = NULL;
    (void)cls;
    if (audio_from_blob(env, data, &bytes, &length, &header, &tones,
                        &count) == R6_OK && (uint32_t)index < count &&
        r6_nub_pcm(bytes, length, &header, &tones[index], &pcm,
                   &size) == R6_OK) {
        out = (*env)->NewByteArray(env, (jsize)size);
        if (out) {
            (*env)->SetByteArrayRegion(env, out, 0, (jsize)size,
                                       (const jbyte *)pcm);
        }
    }
    free(tones);
    free(bytes);
    return out;
}

/* Engine-sound bridge: packed blob in, plain mapping/layer values out. */
JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_EngineSound_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray data) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_esnd_header header;
    jint values[4];
    jintArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK &&
        r6_esnd_parse(bytes, length, &header) == R6_OK) {
        values[0] = (jint)header.mapping_count;
        values[1] = (jint)header.sound_count;
        values[2] = (jint)header.tunes_per_car;
        values[3] = (jint)header.layer_count;
        out = glsl_ints(env, values, 4);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_EngineSound_nativeFind(JNIEnv *env, jclass cls,
                                           jbyteArray data, jint car_type,
                                           jint tune) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_esnd_mapping mapping;
    jint values[20];
    jintArray out = NULL;
    uint32_t i;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK &&
        r6_esnd_find(bytes, length, (uint8_t)car_type, (uint8_t)tune,
                     &mapping) == R6_OK) {
        values[0] = mapping.car_type;
        values[1] = mapping.tune;
        values[2] = mapping.group;
        values[3] = mapping.engine_sound;
        for (i = 0; i < R6_ESND_LAYER_COUNT; i++) {
            values[4 + i] = mapping.tones[i];
        }
        out = glsl_ints(env, values, 20);
    }
    free(bytes);
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_EngineSound_nativeLayer(JNIEnv *env, jclass cls,
                                            jbyteArray data, jint sound,
                                            jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_esnd_layer layer;
    jdouble values[13];
    jdoubleArray out = NULL;
    uint32_t i;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK &&
        r6_esnd_get_layer(bytes, length, (uint16_t)sound, (uint32_t)index,
                          &layer) == R6_OK) {
        values[0] = layer.layer;
        values[1] = layer.source;
        values[2] = layer.flags;
        values[3] = layer.index;
        values[4] = layer.tone;
        for (i = 0; i < 5; i++) {
            values[5 + i] = layer.envelope[i];
        }
        values[10] = layer.rpm_limit;
        values[11] = layer.scale;
        values[12] = layer.base;
        out = (*env)->NewDoubleArray(env, 13);
        if (out) {
            (*env)->SetDoubleArrayRegion(env, out, 0, 13, values);
        }
    }
    free(bytes);
    return out;
}

/* Compiled vertex-layout bridge: blob in, plain attribute values out. */
static int vertex_from_blob(JNIEnv *env, jbyteArray data,
                            unsigned char **bytes, r6_vertex_view *view) {
    size_t length = 0;
    if (raw_from_blob(env, data, bytes, &length) != R6_OK) {
        return R6_ERR_ARG;
    }
    if (r6_vertex_init(view, *bytes, length) != R6_OK) {
        free(*bytes);
        *bytes = NULL;
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_VertexLayout_nativeCount(JNIEnv *env, jclass cls,
                                             jbyteArray data) {
    unsigned char *bytes = NULL;
    r6_vertex_view view;
    jint result = -1;
    (void)cls;
    if (vertex_from_blob(env, data, &bytes, &view) == R6_OK) {
        result = (jint)view.count;
    }
    free(bytes);
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_VertexLayout_nativeAttrib(JNIEnv *env, jclass cls,
                                              jbyteArray data, jint index) {
    unsigned char *bytes = NULL;
    r6_vertex_view view;
    r6_vertex_attrib attrib;
    jint values[5];
    jintArray out = NULL;
    (void)cls;
    if (vertex_from_blob(env, data, &bytes, &view) == R6_OK &&
        r6_vertex_get_attrib(&view, (uint32_t)index, &attrib) == R6_OK) {
        values[0] = (jint)attrib.shader_off;
        values[1] = attrib.location;
        values[2] = attrib.semantic_index;
        values[3] = attrib.mask;
        values[4] = (jint)attrib.semantic_off;
        out = glsl_ints(env, values, 5);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_VertexLayout_nativeFind(JNIEnv *env, jclass cls,
                                            jbyteArray data, jstring shader,
                                            jint location) {
    unsigned char *bytes = NULL;
    r6_vertex_view view;
    r6_vertex_attrib attrib;
    const char *name = NULL;
    jint values[5];
    jintArray out = NULL;
    (void)cls;
    if (!shader || location < 0 || location > 0xffff) {
        return NULL;
    }
    name = (*env)->GetStringUTFChars(env, shader, NULL);
    if (vertex_from_blob(env, data, &bytes, &view) == R6_OK && name &&
        r6_vertex_find(&view, name, (uint16_t)location, &attrib) == R6_OK) {
        values[0] = (jint)attrib.shader_off;
        values[1] = attrib.location;
        values[2] = attrib.semantic_index;
        values[3] = attrib.mask;
        values[4] = (jint)attrib.semantic_off;
        out = glsl_ints(env, values, 5);
    }
    if (name) {
        (*env)->ReleaseStringUTFChars(env, shader, name);
    }
    free(bytes);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_VertexLayout_nativeName(JNIEnv *env, jclass cls,
                                            jbyteArray data, jint offset) {
    unsigned char *bytes = NULL;
    r6_vertex_view view;
    const char *name;
    jstring out = NULL;
    (void)cls;
    if (vertex_from_blob(env, data, &bytes, &view) == R6_OK) {
        name = r6_vertex_name(&view, (uint32_t)offset);
        if (name) {
            out = (*env)->NewStringUTF(env, name);
        }
    }
    free(bytes);
    return out;
}

/* BGM catalog bridge: packed blob in, plain id/name/path values out. */
static jintArray bgm_record_values(JNIEnv *env, const r6_bgm_record *record) {
    jint values[4];
    values[0] = record->id;
    values[1] = record->flags;
    values[2] = (jint)record->name_off;
    values[3] = (jint)record->path_off;
    return glsl_ints(env, values, 4);
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_BgmCatalog_nativeHeader(JNIEnv *env, jclass cls,
                                            jbyteArray data) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_bgm_header header;
    jint values[5];
    jintArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK &&
        r6_bgm_parse(bytes, length, &header) == R6_OK) {
        values[0] = (jint)header.version;
        values[1] = (jint)header.count;
        values[2] = (jint)header.id_first;
        values[3] = (jint)header.strings_off;
        values[4] = (jint)header.strings_size;
        out = glsl_ints(env, values, 5);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_BgmCatalog_nativeFindId(JNIEnv *env, jclass cls,
                                            jbyteArray data, jint id) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_bgm_record record;
    jintArray out = NULL;
    (void)cls;
    if (id >= 0 && id <= 0xffff &&
        raw_from_blob(env, data, &bytes, &length) == R6_OK &&
        r6_bgm_find_id(bytes, length, (uint16_t)id, &record) == R6_OK) {
        out = bgm_record_values(env, &record);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_BgmCatalog_nativeFindName(JNIEnv *env, jclass cls,
                                              jbyteArray data, jstring name) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_bgm_record record;
    const char *text = NULL;
    jintArray out = NULL;
    (void)cls;
    if (!name) {
        return NULL;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK && text &&
        r6_bgm_find_name(bytes, length, text, &record) == R6_OK) {
        out = bgm_record_values(env, &record);
    }
    if (text) {
        (*env)->ReleaseStringUTFChars(env, name, text);
    }
    free(bytes);
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_BgmCatalog_nativeString(JNIEnv *env, jclass cls,
                                            jbyteArray data, jint offset) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    const char *text;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK) {
        text = r6_bgm_string(bytes, length, (uint32_t)offset);
        if (text) {
            out = (*env)->NewStringUTF(env, text);
        }
    }
    free(bytes);
    return out;
}

/* Engine-runtime bridge: the host supplies pow/exp2 from libm, the core
 * stays freestanding and no native pointer crosses JNI. */
static double engine_pow(void *user, double base, double exponent) {
    (void)user;
    return pow(base, exponent);
}

static double engine_exp2(void *user, double exponent) {
    (void)user;
    return pow(2.0, exponent);
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_EngineRuntime_nativeSoundCount(JNIEnv *env, jclass cls,
                                                   jbyteArray data) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_engine_runtime_view view;
    jint result = -1;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) == R6_OK &&
        r6_engine_runtime_init(&view, bytes, length) == R6_OK) {
        result = (jint)view.sound_count;
    }
    free(bytes);
    return result;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_EngineRuntime_nativeEvaluate(
        JNIEnv *env, jclass cls, jbyteArray runtime, jbyteArray engine_sound,
        jint sound, jint rpm, jint current, jint request_offset,
        jboolean flag, jdoubleArray state_values) {
    unsigned char *runtime_bytes = NULL;
    unsigned char *esnd_bytes = NULL;
    size_t runtime_length = 0;
    size_t esnd_length = 0;
    r6_engine_runtime_view view;
    r6_engine_state state;
    r6_envelope_math math_sink = {NULL, engine_pow, engine_exp2};
    r6_engine_layer_result results[R6_ENGINE_LAYER_COUNT];
    double values[38];
    jdouble output[96];
    jdoubleArray out = NULL;
    uint32_t count = 0;
    uint32_t i;
    uint32_t index;
    (void)cls;
    if (!state_values ||
        (*env)->GetArrayLength(env, state_values) != 38) {
        return NULL;
    }
    (*env)->GetDoubleArrayRegion(env, state_values, 0, 38, values);
    if ((*env)->ExceptionCheck(env) ||
        raw_from_blob(env, runtime, &runtime_bytes, &runtime_length) != R6_OK ||
        raw_from_blob(env, engine_sound, &esnd_bytes, &esnd_length) != R6_OK ||
        r6_engine_runtime_init(&view, runtime_bytes, runtime_length) != R6_OK ||
        r6_engine_state_init(&state, (int32_t)rpm) != R6_OK) {
        free(esnd_bytes);
        free(runtime_bytes);
        return NULL;
    }
    state.current = (int32_t)current;
    state.request_offset = (int32_t)request_offset;
    state.flag = flag ? 1u : 0u;
    for (i = 0; i < 5; i++) {
        state.base[i] = values[i];
    }
    for (i = 0; i < R6_ENGINE_LAYER_COUNT; i++) {
        state.layer_base[i] = values[5 + i];
    }
    state.throttle = values[21];
    for (i = 0; i < 3; i++) {
        for (index = 0; index < 3; index++) {
            state.floors[i][index] = values[22 + i * 3 + index];
        }
    }
    state.smooth34 = values[31];
    state.smooth4f = values[32];
    state.smooth20 = values[33];
    state.f134 = values[34];
    state.f2d = values[35];
    state.sub = values[36];
    state.curve_scale = values[37];

    if (r6_engine_eval_layers(&view, esnd_bytes, esnd_length,
                              (uint32_t)sound, &state, &math_sink, results,
                              R6_ENGINE_LAYER_COUNT, &count) == R6_OK) {
        for (i = 0; i < R6_ENGINE_LAYER_COUNT; i++) {
            index = i * 6;
            output[index] = (jdouble)results[i].layer;
            output[index + 1] = (jdouble)results[i].source;
            output[index + 2] = (jdouble)results[i].tone;
            output[index + 3] = (jdouble)results[i].pitch;
            output[index + 4] = (jdouble)results[i].level;
            output[index + 5] = (jdouble)results[i].volume;
        }
        out = (*env)->NewDoubleArray(env, 96);
        if (out) {
            (*env)->SetDoubleArrayRegion(env, out, 0, 96, output);
        }
    }
    free(esnd_bytes);
    free(runtime_bytes);
    return out;
}

/* Voice-request bridge: Java holds the raw 0xa0 bytes and extension blobs.
 * Native pointer fields stay zero; no pointer or audio device crosses JNI. */
static int voice_copy_ext(JNIEnv *env, jbyteArray blob,
                          r6_voice_request *request, int a) {
    unsigned char bytes[0x34];
    jsize size;
    size_t capacity = (size_t)(a ? R6_VOICE_EXT_B_SIZE : R6_VOICE_EXT_A_SIZE);
    if (!blob) {
        return r6_voice_request_set_ext(request, a, NULL, 0);
    }
    size = (*env)->GetArrayLength(env, blob);
    if ((*env)->ExceptionCheck(env) || (size_t)size > capacity) {
        return R6_ERR_ARG;
    }
    if (size) {
        (*env)->GetByteArrayRegion(env, blob, 0, size, (jbyte *)bytes);
        if ((*env)->ExceptionCheck(env)) {
            return R6_ERR_ARG;
        }
    }
    return r6_voice_request_set_ext(request, a, size ? bytes : NULL,
                                    (size_t)size);
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_VoiceRequest_nativeBuild(
        JNIEnv *env, jclass cls, jint request, jint bank, jint tone,
        jint bank_info, jint chain_tone, jint extended, jbyteArray ext_a,
        jbyteArray ext_b, jdouble volume, jdouble pan, jint flags,
        jdouble extra_a, jdouble extra_b, jdouble extra_c) {
    r6_voice_request record;
    unsigned char raw[R6_VOICE_REQUEST_SIZE];
    jbyteArray out = NULL;
    (void)cls;
    if (r6_voice_request_init(&record) != R6_OK) {
        return NULL;
    }
    record.request = (int32_t)request;
    record.bank = (int32_t)bank;
    record.bank_info = (int32_t)bank_info;
    record.tone = (uint32_t)tone;
    record.chain_tone = (int32_t)chain_tone;
    record.extended = (uint32_t)extended;
    record.volume = (float)volume;
    record.pan = (float)pan;
    record.flags = (uint32_t)flags;
    record.extra_a = (float)extra_a;
    record.extra_b = (float)extra_b;
    record.extra_c = (float)extra_c;
    if (voice_copy_ext(env, ext_a, &record, 0) != R6_OK ||
        voice_copy_ext(env, ext_b, &record, 1) != R6_OK ||
        r6_voice_request_pack(&record, raw, sizeof(raw)) != R6_OK) {
        return NULL;
    }
    out = (*env)->NewByteArray(env, (jsize)sizeof(raw));
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, (jsize)sizeof(raw),
                                   (const jbyte *)raw);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_VoiceRequest_nativeFields(JNIEnv *env, jclass cls,
                                              jbyteArray data) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_voice_request record;
    jdouble values[13];
    jdoubleArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_voice_request_unpack(bytes, length, &record) != R6_OK) {
        free(bytes);
        return NULL;
    }
    values[0] = (jdouble)record.request;
    values[1] = (jdouble)record.bank;
    values[2] = (jdouble)record.bank_info;
    values[3] = (jdouble)record.tone;
    values[4] = (jdouble)record.chain_tone;
    values[5] = (jdouble)record.extended;
    values[6] = (jdouble)record.reserved;
    values[7] = (jdouble)record.volume;
    values[8] = (jdouble)record.pan;
    values[9] = (jdouble)record.flags;
    values[10] = (jdouble)record.extra_a;
    values[11] = (jdouble)record.extra_b;
    values[12] = (jdouble)record.extra_c;
    out = (*env)->NewDoubleArray(env, 13);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 13, values);
    }
    free(bytes);
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_VoiceRequest_nativeExt(JNIEnv *env, jclass cls,
                                           jbyteArray data, jboolean a) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_voice_request record;
    const unsigned char *slot;
    jsize size;
    jbyteArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_voice_request_unpack(bytes, length, &record) != R6_OK) {
        free(bytes);
        return NULL;
    }
    slot = a ? record.ext_b : record.ext_a;
    size = (jsize)(a ? R6_VOICE_EXT_B_SIZE : R6_VOICE_EXT_A_SIZE);
    out = (*env)->NewByteArray(env, size);
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, size, (const jbyte *)slot);
    }
    free(bytes);
    return out;
}

/* config_3d bridge: Java owns the bin bytes and receives plain values. The
 * parser writes into a stack section array; nothing native escapes. */
static int config3d_load(JNIEnv *env, jbyteArray data, unsigned char **bytes,
                         r6_config_3d_view *view,
                         r6_config_3d_section *sections) {
    size_t length = 0;
    int rc = raw_from_blob(env, data, bytes, &length);
    if (rc != R6_OK) {
        return rc;
    }
    return r6_config_3d_init(view, *bytes, length, sections,
                             R6_CONFIG_3D_SECTION_MAX);
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Config3D_nativeHeader(JNIEnv *env, jclass cls,
                                          jbyteArray data) {
    r6_config_3d_view view;
    r6_config_3d_section sections[R6_CONFIG_3D_SECTION_MAX];
    unsigned char *bytes = NULL;
    jint values[5];
    jintArray out = NULL;
    uint32_t i;
    (void)cls;
    if (config3d_load(env, data, &bytes, &view, sections) != R6_OK) {
        free(bytes);
        return NULL;
    }
    for (i = 0; i < 3; i++) {
        values[i] = (jint)view.version[i];
    }
    values[3] = (jint)view.count;
    values[4] = (jint)view.stride;
    out = (*env)->NewIntArray(env, 5);
    if (out) {
        (*env)->SetIntArrayRegion(env, out, 0, 5, values);
    }
    free(bytes);
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_Config3D_nativeGlobals(JNIEnv *env, jclass cls,
                                           jbyteArray data) {
    r6_config_3d_view view;
    r6_config_3d_section sections[R6_CONFIG_3D_SECTION_MAX];
    unsigned char *bytes = NULL;
    jdouble values[4];
    jdoubleArray out = NULL;
    uint32_t i;
    (void)cls;
    if (config3d_load(env, data, &bytes, &view, sections) != R6_OK) {
        free(bytes);
        return NULL;
    }
    for (i = 0; i < 4; i++) {
        values[i] = (jdouble)view.floats[i];
    }
    out = (*env)->NewDoubleArray(env, 4);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 4, values);
    }
    free(bytes);
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_Config3D_nativeRecord(JNIEnv *env, jclass cls,
                                          jbyteArray data, jint section,
                                          jint record) {
    r6_config_3d_view view;
    r6_config_3d_section sections[R6_CONFIG_3D_SECTION_MAX];
    unsigned char *bytes = NULL;
    const r6_config_3d_record *row;
    jdouble values[7];
    jdoubleArray out = NULL;
    uint32_t i;
    (void)cls;
    if (config3d_load(env, data, &bytes, &view, sections) != R6_OK ||
        section < 0 || (uint32_t)section >= view.count ||
        record < 0 || record >= R6_CONFIG_3D_RECORD_COUNT) {
        free(bytes);
        return NULL;
    }
    row = &sections[section].records[record];
    values[0] = (jdouble)row->flags;
    values[1] = (jdouble)row->db_start;
    values[2] = (jdouble)row->angle;
    values[3] = (jdouble)row->db_end;
    for (i = 0; i < 3; i++) {
        values[4 + i] = (jdouble)row->raw[i];
    }
    out = (*env)->NewDoubleArray(env, 7);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 7, values);
    }
    free(bytes);
    return out;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_Config3D_nativeTail(JNIEnv *env, jclass cls,
                                        jbyteArray data, jint section) {
    r6_config_3d_view view;
    r6_config_3d_section sections[R6_CONFIG_3D_SECTION_MAX];
    unsigned char *bytes = NULL;
    jint values[R6_CONFIG_3D_TAIL_COUNT];
    jintArray out = NULL;
    uint32_t i;
    (void)cls;
    if (config3d_load(env, data, &bytes, &view, sections) != R6_OK ||
        section < 0 || (uint32_t)section >= view.count) {
        free(bytes);
        return NULL;
    }
    for (i = 0; i < R6_CONFIG_3D_TAIL_COUNT; i++) {
        values[i] = (jint)sections[section].tail[i];
    }
    out = (*env)->NewIntArray(env, R6_CONFIG_3D_TAIL_COUNT);
    if (out) {
        (*env)->SetIntArrayRegion(env, out, 0, R6_CONFIG_3D_TAIL_COUNT,
                                  values);
    }
    free(bytes);
    return out;
}

JNIEXPORT jdouble JNICALL
Java_com_wmmt_re6rr_Config3D_nativeAmplitude(JNIEnv *env, jclass cls,
                                             jdouble db, jdouble zero_db) {
    r6_envelope_math math_sink = {NULL, engine_pow, engine_exp2};
    double value = 0.0;
    (void)env;
    (void)cls;
    if (r6_config_3d_amplitude(&math_sink, db, zero_db, &value) != R6_OK) {
        return 0.0;
    }
    return (jdouble)value;
}

/* Bank-registration bridge: the first call sizes the caller-owned tone array,
 * then the core fills it. Only copied values cross JNI. */
static int bank_setup_parse(JNIEnv *env, jbyteArray data,
                            r6_bank_setup_view *view,
                            r6_bank_setup_tone **tones) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    size_t count;
    int rc = raw_from_blob(env, data, &bytes, &length);
    if (rc != R6_OK) {
        return rc;
    }
    *tones = NULL;
    rc = r6_bank_setup_init(view, bytes, length, NULL, 0);
    if (rc == R6_OK) {
        free(bytes);
        return R6_OK;
    }
    if (rc != R6_ERR_BUFFER) {
        free(bytes);
        return rc;
    }
    count = (size_t)view->tone_count;
    if (count > (size_t)-1 / sizeof(**tones)) {
        free(bytes);
        return R6_ERR_MEMORY;
    }
    *tones = (r6_bank_setup_tone *)malloc(count ? count * sizeof(**tones) : 1);
    if (!*tones) {
        free(bytes);
        return R6_ERR_MEMORY;
    }
    rc = r6_bank_setup_init(view, bytes, length, *tones, count);
    free(bytes);
    if (rc != R6_OK) {
        free(*tones);
        *tones = NULL;
    }
    return rc;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_BankSetup_nativeHeader(JNIEnv *env, jclass cls,
                                           jbyteArray data) {
    r6_bank_setup_view view;
    r6_bank_setup_tone *tones = NULL;
    jint values[8];
    jintArray out = NULL;
    uint32_t i;
    (void)cls;
    if (bank_setup_parse(env, data, &view, &tones) != R6_OK) {
        free(tones);
        return NULL;
    }
    for (i = 0; i < 3; i++) {
        values[i] = (jint)view.version[i];
    }
    values[3] = (jint)view.tone_count;
    values[4] = (jint)view.data_offset;
    values[5] = (jint)view.data_size;
    values[6] = (jint)view.record_table;
    values[7] = (jint)(tones ? 1 : 0);
    out = (*env)->NewIntArray(env, 8);
    if (out) {
        (*env)->SetIntArrayRegion(env, out, 0, 8, values);
    }
    free(tones);
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_BankSetup_nativeTone(JNIEnv *env, jclass cls,
                                         jbyteArray data, jint index) {
    r6_bank_setup_view view;
    r6_bank_setup_tone *tones = NULL;
    jdouble values[3];
    jdoubleArray out = NULL;
    (void)cls;
    if (bank_setup_parse(env, data, &view, &tones) != R6_OK ||
        index < 0 || (uint32_t)index >= view.tone_count) {
        free(tones);
        return NULL;
    }
    values[0] = (jdouble)tones[index].length;
    values[1] = (jdouble)tones[index].data_offset;
    values[2] = (jdouble)tones[index].formats;
    out = (*env)->NewDoubleArray(env, 3);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 3, values);
    }
    free(tones);
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_AudioStream_nativeFadeMs(JNIEnv *env, jclass cls,
                                             jint now_frame,
                                             jint max_frame) {
    (void)env;
    (void)cls;
    return (jint)r6_audio_fade_frames_to_ms((int32_t)now_frame,
                                            (int32_t)max_frame);
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_AudioStream_nativeReserve(JNIEnv *env, jclass cls,
                                              jlong total, jlong size) {
    (void)env;
    (void)cls;
    return (jlong)r6_audio_stream_reserve((int64_t)total, (int64_t)size);
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SoundInit_nativeParse(JNIEnv *env, jclass cls,
                                          jbyteArray data) {
    r6_sound_init config;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[10];
    jlongArray out = NULL;
    uint32_t i;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_sound_init_parse(bytes, length, &config) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)config.bank_num;
    values[1] = (jlong)config.reqid_num;
    values[2] = (jlong)config.stream_num;
    for (i = 0; i < 3; i++) {
        values[3 + i] = (jlong)config.pointers[i];
    }
    values[6] = (jlong)config.bank_bytes;
    values[7] = (jlong)config.request_bytes;
    values[8] = (jlong)config.stream_bytes;
    values[9] = (jlong)R6_SOUND_IMPL_SIZE;
    out = (*env)->NewLongArray(env, 10);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 10, values);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_BgmFade_nativeRead(JNIEnv *env, jclass cls,
                                       jbyteArray stream) {
    r6_bgm_fade_state state;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jdouble values[9];
    jdoubleArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, stream, &bytes, &length) != R6_OK ||
        r6_bgm_fade_read(bytes, length, &state) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jdouble)state.state;
    values[1] = (jdouble)state.flag;
    values[2] = (jdouble)state.mode;
    values[3] = (jdouble)state.frames;
    values[4] = (jdouble)state.step;
    values[5] = (jdouble)state.volume;
    values[6] = (jdouble)state.voice;
    values[7] = (jdouble)state.channel;
    values[8] = (jdouble)state.fader;
    out = (*env)->NewDoubleArray(env, 9);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 9, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_BgmFade_nativeBegin(JNIEnv *env, jclass cls,
                                        jbyteArray stream, jint ms) {
    r6_bgm_fade_state state;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t stop_voice = 0;
    uint32_t status;
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, stream, &bytes, &length) != R6_OK) {
        return NULL;
    }
    status = r6_bgm_fade_begin(bytes, length, (int32_t)ms, &stop_voice);
    if (r6_bgm_fade_read(bytes, length, &state) == R6_OK) {
        (*env)->SetByteArrayRegion(env, stream, 0, (jsize)length,
                                   (const jbyte *)bytes);
    }
    free(bytes);
    values[0] = (jlong)status;
    values[1] = (jlong)stop_voice;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_BgmManager_nativeRead(JNIEnv *env, jclass cls,
                                          jbyteArray data) {
    r6_bgm_manager_state state;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_bgm_manager_read(bytes, length, &state) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)state.current;
    values[1] = (jlong)state.next;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_BgmManager_nativeSelect(JNIEnv *env, jclass cls,
                                            jbyteArray data, jint id) {
    r6_bgm_manager_state state;
    unsigned char *bytes = NULL;
    size_t length = 0;
    int32_t action = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_bgm_manager_select(bytes, length, (int32_t)id, &action) != R6_OK ||
        r6_bgm_manager_read(bytes, length, &state) != R6_OK) {
        free(bytes);
        return NULL;
    }
    (*env)->SetByteArrayRegion(env, data, 0, (jsize)length,
                               (const jbyte *)bytes);
    free(bytes);
    values[0] = (jlong)action;
    values[1] = (jlong)state.current;
    values[2] = (jlong)state.next;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SoundDispatch_nativeBank(JNIEnv *env, jclass cls,
                                             jbyteArray data, jint index) {
    r6_sound_bank_slot_t slot;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_sound_bank_slot(bytes, length, (uint32_t)index, &slot) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)slot.handle;
    values[1] = (jlong)slot.state;
    values[2] = (jlong)slot.ready;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SoundDispatch_nativeLoop(JNIEnv *env, jclass cls,
                                             jbyteArray data, jint index) {
    r6_sound_loop_record_t record;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[2];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_sound_loop_record(bytes, length, (uint32_t)index, &record) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)record.flag;
    values[1] = (jlong)record.tone;
    out = (*env)->NewLongArray(env, 2);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 2, values);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_SoundDispatch_nativePositional(JNIEnv *env, jclass cls,
                                                   jbyteArray data,
                                                   jint index) {
    r6_sound_positional_record_t record;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jdouble values[6];
    jdoubleArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_sound_positional_record(bytes, length, (uint32_t)index,
                                   &record) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jdouble)record.bank;
    values[1] = (jdouble)record.tone;
    values[2] = (jdouble)record.frames;
    values[3] = (jdouble)record.x;
    values[4] = (jdouble)record.y;
    values[5] = (jdouble)record.z;
    out = (*env)->NewDoubleArray(env, 6);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 6, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SoundConfig_nativeParse(JNIEnv *env, jclass cls,
                                            jbyteArray data) {
    r6_sound_bin config;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[3 + 2 * R6_SOUND_BIN_SECTIONS];
    jlongArray out = NULL;
    uint32_t i;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_sound_bin_parse(bytes, length, &config) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)config.size;
    values[1] = (jlong)config.header_size;
    values[2] = (jlong)config.float_offset;
    for (i = 0; i < R6_SOUND_BIN_SECTIONS; i++) {
        values[3 + i] = (jlong)config.counts[i];
        values[3 + R6_SOUND_BIN_SECTIONS + i] = (jlong)config.offsets[i];
    }
    out = (*env)->NewLongArray(env, 3 + 2 * R6_SOUND_BIN_SECTIONS);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0,
                                   3 + 2 * R6_SOUND_BIN_SECTIONS, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SoundStrings_nativeHeader(JNIEnv *env, jclass cls,
                                              jbyteArray blob, jint kind) {
    r6_sound_strings_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[8];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_sound_strings_parse(bytes, length, (int)kind, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.bank_id;
    values[2] = (jlong)header.count;
    values[3] = (jlong)header.size;
    values[4] = (jlong)header.name_size;
    values[5] = (jlong)header.path_size;
    values[6] = (jlong)header.rows_off;
    values[7] = (jlong)header.row_size;
    out = (*env)->NewLongArray(env, 8);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 8, values);
    }
    return out;
}

JNIEXPORT jobjectArray JNICALL
Java_com_wmmt_re6rr_SoundStrings_nativeRow(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint kind,
                                           jint index) {
    r6_sound_strings_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jobjectArray out = NULL;
    jclass string_class;
    jstring value;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_sound_strings_row(bytes, length, (int)kind, (uint32_t)index,
                             &row) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    string_class = (*env)->FindClass(env, "java/lang/String");
    if (string_class) {
        out = (*env)->NewObjectArray(env, 2, string_class, NULL);
    }
    if (!out) {
        return NULL;
    }
    value = (*env)->NewStringUTF(env, row.name);
    if (value) {
        (*env)->SetObjectArrayElement(env, out, 0, value);
        (*env)->DeleteLocalRef(env, value);
    }
    value = (*env)->NewStringUTF(env, row.value);
    if (value) {
        (*env)->SetObjectArrayElement(env, out, 1, value);
        (*env)->DeleteLocalRef(env, value);
    }
    return out;
}

JNIEXPORT jlong JNICALL
Java_com_wmmt_re6rr_SoundStrings_nativeRowId(JNIEnv *env, jclass cls,
                                             jbyteArray blob, jint kind,
                                             jint index) {
    r6_sound_strings_row_t row;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong result = -1;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) == R6_OK &&
        r6_sound_strings_row(bytes, length, (int)kind, (uint32_t)index,
                             &row) == R6_OK) {
        result = (jlong)row.id;
    }
    free(bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_LuaAudioBindings_nativeCount(JNIEnv *env, jclass cls) {
    (void)env;
    (void)cls;
    return (jint)r6_audio_binding_count();
}

JNIEXPORT jobjectArray JNICALL
Java_com_wmmt_re6rr_LuaAudioBindings_nativeNames(JNIEnv *env, jclass cls,
                                                 jint index) {
    r6_audio_binding_t binding;
    jobjectArray out = NULL;
    jclass string_class;
    jstring value;
    (void)cls;
    if (r6_audio_binding((uint32_t)index, &binding) != R6_OK) {
        return NULL;
    }
    string_class = (*env)->FindClass(env, "java/lang/String");
    if (string_class) {
        out = (*env)->NewObjectArray(env, 2, string_class, NULL);
    }
    if (!out) {
        return NULL;
    }
    value = (*env)->NewStringUTF(env, binding.name);
    if (value) {
        (*env)->SetObjectArrayElement(env, out, 0, value);
        (*env)->DeleteLocalRef(env, value);
    }
    value = (*env)->NewStringUTF(env, binding.call);
    if (value) {
        (*env)->SetObjectArrayElement(env, out, 1, value);
        (*env)->DeleteLocalRef(env, value);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_LuaAudioBindings_nativeNumbers(JNIEnv *env, jclass cls,
                                                   jint index) {
    r6_audio_binding_t binding;
    jlong values[3];
    jlongArray out = NULL;
    (void)cls;
    if (r6_audio_binding((uint32_t)index, &binding) != R6_OK) {
        return NULL;
    }
    values[0] = (jlong)binding.address;
    values[1] = (jlong)binding.bank;
    values[2] = (jlong)binding.tone;
    out = (*env)->NewLongArray(env, 3);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 3, values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_LuaAudioBindings_nativeFind(JNIEnv *env, jclass cls,
                                                jstring name) {
    const char *text;
    int found;
    (void)cls;
    if (!name) {
        return -1;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        return -1;
    }
    found = r6_audio_binding_find(text, NULL);
    (*env)->ReleaseStringUTFChars(env, name, text);
    return found >= 0 ? (jint)found : -1;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_BankSlots_nativeFind(JNIEnv *env, jclass cls,
                                         jbyteArray slots) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t index = 0;
    jint result;
    (void)cls;
    if (raw_from_blob(env, slots, &bytes, &length) != R6_OK) {
        return -1;
    }
    result = r6_bank_slot_find(bytes, length, &index) == R6_OK ? (jint)index :
                                                                -1;
    free(bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_CourseSurface_nativeClassify(JNIEnv *env, jclass cls,
                                                 jstring name) {
    const char *text;
    jint result;
    (void)cls;
    if (!name) {
        return -1;
    }
    text = (*env)->GetStringUTFChars(env, name, NULL);
    if (!text) {
        return -1;
    }
    result = (jint)r6_course_classify_surface(text);
    (*env)->ReleaseStringUTFChars(env, name, text);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_SceneBridge_nativeWriteCamid(JNIEnv *env, jclass cls,
                                                 jbyteArray scene,
                                                 jbyteArray config) {
    unsigned char *scene_bytes = NULL;
    unsigned char *config_bytes = NULL;
    size_t scene_size = 0;
    size_t config_size = 0;
    int32_t camid = 0;
    jint result;
    (void)cls;
    if (raw_from_blob(env, scene, &scene_bytes, &scene_size) != R6_OK) {
        return -1;
    }
    if (raw_from_blob(env, config, &config_bytes, &config_size) != R6_OK) {
        free(scene_bytes);
        return -1;
    }
    result = r6_scene_write_camid(scene_bytes, scene_size, config_bytes,
                                  config_size, &camid) == R6_OK ? camid : -1;
    if (result >= 0) {
        (*env)->SetByteArrayRegion(env, config, 0, (jsize)config_size,
                                   (const jbyte *)config_bytes);
    }
    free(config_bytes);
    free(scene_bytes);
    return result;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_SceneBridge_nativeContainerOffset(JNIEnv *env, jclass cls,
                                                      jint slot) {
    size_t offset = 0;
    (void)env;
    (void)cls;
    if (r6_scene_container_offset((uint32_t)slot, &offset) != R6_OK) {
        return -1;
    }
    return (jint)offset;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_SceneBridge_nativeRuntimeCamera(JNIEnv *env, jclass cls,
                                                    jbyteArray records,
                                                    jint frame) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    jint result;
    (void)cls;
    if (raw_from_blob(env, records, &bytes, &length) != R6_OK) {
        return -1;
    }
    result = (jint)r6_scene_runtime_camera(bytes, length, (int32_t)frame);
    free(bytes);
    return result;
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_EesContainer_nativeParse(JNIEnv *env, jclass cls,
                                             jbyteArray raw) {
    r6_ees_header_t header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jint values[22];
    jintArray out = NULL;
    uint32_t index;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_ees_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jint)header.kind;
    values[1] = (jint)header.version;
    values[2] = (jint)header.file_size;
    values[3] = (jint)header.count;
    values[4] = (jint)header.effect_count;
    values[5] = (jint)header.header_size;
    values[6] = (jint)header.array_count;
    for (index = 0; index < R6_EES_ARRAY_MAX; index++) {
        values[7u + index * 5u] = (jint)header.arrays[index].name;
        values[8u + index * 5u] = (jint)header.arrays[index].count;
        values[9u + index * 5u] = (jint)header.arrays[index].stride;
        values[10u + index * 5u] = (jint)header.arrays[index].offset;
        values[11u + index * 5u] = (jint)header.arrays[index].size;
    }
    out = (*env)->NewIntArray(env, 22);
    if (out) {
        (*env)->SetIntArrayRegion(env, out, 0, 22, values);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_EmtisTable_nativeParse(JNIEnv *env, jclass cls,
                                           jbyteArray raw) {
    r6_emtis_t table;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jdouble values[258];
    jdoubleArray out = NULL;
    uint32_t index;
    uint32_t part;
    uint32_t at;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_emtis_parse(bytes, length, &table) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    for (index = 0; index < 258u; index++) {
        values[index] = 0.0;
    }
    values[0] = (jdouble)table.version_count;
    for (index = 0; index < table.version_count; index++) {
        values[1u + index] = (jdouble)table.version[index];
    }
    values[9] = (jdouble)table.header_count;
    for (index = 0; index < table.header_count; index++) {
        values[10u + index] = table.header[index];
    }
    values[74] = (jdouble)table.token_count;
    values[75] = (jdouble)table.section_count;
    for (index = 0; index < table.section_count; index++) {
        at = 76u + index * 11u;
        values[at] = (jdouble)table.sections[index].marker;
        values[at + 1u] = (jdouble)table.sections[index].start;
        values[at + 2u] = (jdouble)table.sections[index].length;
        for (part = 0; part < R6_EMTIS_SECTION_HEAD; part++) {
            values[at + 3u + part] = table.sections[index].head[part];
        }
    }
    values[252] = (jdouble)table.name_count;
    for (index = 0; index < R6_EMTIS_NAME_PREFIXES; index++) {
        values[253u + index] = (jdouble)table.name_counts[index];
    }
    out = (*env)->NewDoubleArray(env, 258);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 258, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EngmapTable_nativeParse(JNIEnv *env, jclass cls,
                                            jbyteArray raw) {
    r6_engmap_t table;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[1 + R6_ENGMAP_MAX_PAIRS * 2];
    jlongArray out = NULL;
    uint32_t index;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_engmap_parse(bytes, length, &table) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)table.count;
    for (index = 0; index < R6_ENGMAP_MAX_PAIRS; index++) {
        values[1u + index * 2u] = (jlong)table.pairs[index].engine_sound;
        values[2u + index * 2u] = (jlong)table.pairs[index].group;
    }
    out = (*env)->NewLongArray(env, (jsize)(1u + R6_ENGMAP_MAX_PAIRS * 2u));
    if (out) {
        (*env)->SetLongArrayRegion(
            env, out, 0, (jsize)(1u + R6_ENGMAP_MAX_PAIRS * 2u), values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_NshContainer_nativeParse(JNIEnv *env, jclass cls,
                                             jbyteArray raw) {
    r6_nsh_t nsh;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[98];
    jlongArray out = NULL;
    uint32_t index;
    uint32_t chunk;
    uint32_t word;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_nsh_parse(bytes, length, &nsh) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)nsh.file_size;
    values[1] = (jlong)nsh.version;
    values[2] = (jlong)nsh.subversion;
    values[3] = (jlong)nsh.flags;
    values[4] = (jlong)nsh.record_count;
    for (index = 0; index < 5u; index++) {
        values[5u + index] = (jlong)nsh.table[index];
    }
    for (index = 0; index < R6_NSH_RECORD_MAX; index++) {
        const r6_nsh_record_t *record = &nsh.records[index];
        jlong *row = values + 10u + index * 44u;
        row[0] = (jlong)record->offset;
        row[1] = (jlong)record->count;
        row[2] = (jlong)record->dxbc_size;
        row[3] = (jlong)record->reserved;
        row[4] = (jlong)record->dxbc_offset;
        row[5] = (jlong)record->dxbc_version;
        row[6] = (jlong)record->dxbc_actual_size;
        row[7] = (jlong)record->chunk_count;
        for (word = 0; word < 4u; word++) {
            row[8u + word] = (jlong)(
                (uint32_t)record->digest[word * 4u] |
                ((uint32_t)record->digest[word * 4u + 1u] << 8) |
                ((uint32_t)record->digest[word * 4u + 2u] << 16) |
                ((uint32_t)record->digest[word * 4u + 3u] << 24));
        }
        for (chunk = 0; chunk < R6_NSH_CHUNK_MAX; chunk++) {
            row[12u + chunk * 4u] = (jlong)record->chunks[chunk].tag;
            row[13u + chunk * 4u] = (jlong)record->chunks[chunk].offset;
            row[14u + chunk * 4u] = (jlong)record->chunks[chunk].size;
            row[15u + chunk * 4u] = (jlong)record->chunks[chunk].data_offset;
        }
    }
    out = (*env)->NewLongArray(env, 98);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 98, values);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_EesCamera_nativeFields(JNIEnv *env, jclass cls,
                                           jbyteArray raw, jint offset) {
    r6_ees_camera_fields_t fields;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jdouble values[R6_EES_CAMERA_FIELD_COUNT];
    jdoubleArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_ees_camera_fields(bytes, length, (uint32_t)offset, &fields) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jdouble)fields.m_CamType;
    values[1] = (jdouble)fields.m_StratFrame;
    values[2] = (jdouble)fields.m_ActFrame;
    values[3] = (jdouble)fields.m_WiatMode;
    values[4] = (jdouble)fields.m_StratFieldAngle;
    values[5] = (jdouble)fields.m_EndFieldAngle;
    values[6] = (jdouble)fields.m_FieldAngleCalcId;
    values[7] = (jdouble)fields.m_GlobalLookAt;
    values[8] = (jdouble)fields.m_LookAtId;
    values[9] = (jdouble)fields.m_LookAtStartRenge;
    values[10] = (jdouble)fields.m_LookAtStartCamRotX;
    values[11] = (jdouble)fields.m_LookAtStartCamRotY;
    values[12] = (jdouble)fields.m_LookAtStartCamRotZ;
    values[13] = (jdouble)fields.m_LookAtEndRenge;
    values[14] = (jdouble)fields.m_LookAtEndCamRotX;
    values[15] = (jdouble)fields.m_LookAtEndCamRotY;
    values[16] = (jdouble)fields.m_LookAtEndCamRotZ;
    values[17] = (jdouble)fields.m_TransCalcId;
    values[18] = (jdouble)fields.m_RotCalcId;
    values[19] = (jdouble)fields.m_StratOpRotZ;
    values[20] = (jdouble)fields.m_EndOpRotZ;
    values[21] = (jdouble)fields.m_OpRotZCalcId;
    values[22] = (jdouble)fields.m_LookAtStartOfsetPosX;
    values[23] = (jdouble)fields.m_LookAtStartOfsetPosY;
    values[24] = (jdouble)fields.m_LookAtStartOfsetPosZ;
    values[25] = (jdouble)fields.m_LookAtEndOfsetPosX;
    values[26] = (jdouble)fields.m_LookAtEndOfsetPosY;
    values[27] = (jdouble)fields.m_LookAtEndOfsetPosZ;
    values[28] = (jdouble)fields.m_OfsetCalcId;
    values[29] = (jdouble)fields.m_StartConnection;
    values[30] = (jdouble)fields.m_EndConnection;
    out = (*env)->NewDoubleArray(env, R6_EES_CAMERA_FIELD_COUNT);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, R6_EES_CAMERA_FIELD_COUNT,
                                     values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_EesCamera_nativeAcceptsType(JNIEnv *env, jclass cls,
                                                jint type) {
    (void)env;
    (void)cls;
    return (jint)r6_ees_camera_accept_type((int32_t)type);
}

JNIEXPORT jintArray JNICALL
Java_com_wmmt_re6rr_EesCarInfo_nativeRead(JNIEnv *env, jclass cls,
                                          jbyteArray raw, jint offset) {
    int32_t value = 0;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jint values[1];
    jintArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_ees_car_info(bytes, length, (uint32_t)offset, &value) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jint)value;
    out = (*env)->NewIntArray(env, 1);
    if (out) {
        (*env)->SetIntArrayRegion(env, out, 0, 1, values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_EesCamera_nativeAtFrame(JNIEnv *env, jclass cls,
                                            jbyteArray raw, jint offset,
                                            jint count, jint frame) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    jint result;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK) {
        return -1;
    }
    result = (jint)r6_ees_camera_at_frame(bytes, length, (uint32_t)offset,
                                          (uint32_t)count, (int32_t)frame);
    free(bytes);
    return result;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_EesCarEffect_nativeCopy(JNIEnv *env, jclass cls,
                                            jbyteArray record) {
    unsigned char target[R6_EES_CAR_EFFECT_COPY_SIZE];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jbyteArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, record, &bytes, &length) != R6_OK ||
        r6_ees_car_effect_copy(bytes, length, target,
                               sizeof(target)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewByteArray(env, (jsize)sizeof(target));
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, (jsize)sizeof(target),
                                   (const jbyte *)target);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_EesCarDisp_nativeRead(JNIEnv *env, jclass cls,
                                          jbyteArray raw, jint offset) {
    r6_ees_car_disp_t record;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jdouble values[20];
    jdoubleArray out = NULL;
    uint32_t index;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_ees_car_disp(bytes, length, (uint32_t)offset, &record) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jdouble)record.car_id;
    values[1] = (jdouble)record.flags;
    for (index = 0; index < R6_EES_CAR_DISP_MATRIX_FLOATS; index++) {
        values[2u + index] = (jdouble)record.matrix[index];
    }
    values[18] = (jdouble)record.yaw;
    values[19] = (jdouble)record.yaw_units;
    out = (*env)->NewDoubleArray(env, 20);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 20, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_EnvironmentLua_nativeParse(JNIEnv *env, jclass cls,
                                               jbyteArray raw) {
    r6_scene_values_t values;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong out_values[8];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, raw, &bytes, &length) != R6_OK ||
        r6_environment_parse(bytes, length, &values) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out_values[0] = (jlong)values.stage;
    out_values[1] = (jlong)values.stage_root;
    out_values[2] = (jlong)values.stage_day;
    out_values[3] = (jlong)values.cam_id;
    out_values[4] = (jlong)values.actors[0];
    out_values[5] = (jlong)values.actors[1];
    out_values[6] = (jlong)values.actors[2];
    out_values[7] = (jlong)values.actors[3];
    out = (*env)->NewLongArray(env, 8);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 8, out_values);
    }
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_SceneConfig_nativePack(JNIEnv *env, jclass cls,
                                           jint stage, jint stage_root,
                                           jint stage_day, jint cam_id,
                                           jintArray actors) {
    r6_scene_values_t values;
    unsigned char scene[R6_SCENE_SIZE];
    jint *source;
    jsize count;
    jbyteArray out = NULL;
    jsize index;
    (void)cls;
    if (!actors) {
        return NULL;
    }
    count = (*env)->GetArrayLength(env, actors);
    if (count < 4) {
        return NULL;
    }
    source = (*env)->GetIntArrayElements(env, actors, NULL);
    if (!source) {
        return NULL;
    }
    values.stage = (int32_t)stage;
    values.stage_root = (int32_t)stage_root;
    values.stage_day = (int32_t)stage_day;
    values.cam_id = (int32_t)cam_id;
    for (index = 0; index < 4; index++) {
        values.actors[index] = (int32_t)source[index];
    }
    (*env)->ReleaseIntArrayElements(env, actors, source, JNI_ABORT);
    if (r6_scene_pack(&values, scene, sizeof(scene)) != R6_OK) {
        return NULL;
    }
    out = (*env)->NewByteArray(env, (jsize)sizeof(scene));
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, (jsize)sizeof(scene),
                                   (const jbyte *)scene);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_NativeNames_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    r6_native_names_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[20];
    jlongArray out = NULL;
    uint32_t index;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_native_names_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    for (index = 0; index < R6_NATIVE_NAMES_KINDS; index++) {
        values[index] = (jlong)header.counts[index];
        values[9u + index] = (jlong)header.offsets[index];
    }
    values[18] = (jlong)header.strings_off;
    values[19] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 20);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 20, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_NativeNames_nativeName(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint kind,
                                           jint index) {
    char name[0x100];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_native_names_get(bytes, length, (int)kind, (uint32_t)index,
                            name, sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_SceneConfig_nativeHeader(JNIEnv *env, jclass cls,
                                             jbyteArray blob) {
    r6_scene_names_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[4];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_scene_names_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.counts[R6_SCENE_CAR_NAMES];
    values[1] = (jlong)header.counts[R6_SCENE_STAGE_NAMES];
    values[2] = (jlong)header.counts[R6_SCENE_DAY_NAMES];
    values[3] = (jlong)header.strings_off;
    out = (*env)->NewLongArray(env, 4);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 4, values);
    }
    return out;
}

JNIEXPORT jstring JNICALL
Java_com_wmmt_re6rr_SceneConfig_nativeName(JNIEnv *env, jclass cls,
                                           jbyteArray blob, jint kind,
                                           jint value) {
    char name[0x80];
    unsigned char *bytes = NULL;
    size_t length = 0;
    jstring out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_scene_names_get(bytes, length, (int)kind, (int32_t)value,
                           name, sizeof(name)) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    out = (*env)->NewStringUTF(env, name);
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_AudioLayoutFacts_nativeAll(JNIEnv *env, jclass cls) {
    r6_audio_layout_facts_t facts;
    jlong values[17];
    jlongArray out = NULL;
    (void)cls;
    r6_audio_layout_facts(&facts);
    values[0] = (jlong)facts.bank_slots;
    values[1] = (jlong)facts.slot_stride;
    values[2] = (jlong)facts.slot_bank_ptr;
    values[3] = (jlong)facts.slot_data_ptr;
    values[4] = (jlong)facts.slot_voice_ids;
    values[5] = (jlong)facts.record_base;
    values[6] = (jlong)facts.record_stride;
    values[7] = (jlong)facts.record_voice_ids;
    values[8] = (jlong)facts.stream_reserve;
    values[9] = (jlong)facts.stream_limit;
    values[10] = (jlong)facts.version[0];
    values[11] = (jlong)facts.version[1];
    values[12] = (jlong)facts.version[2];
    values[13] = (jlong)facts.voice_slots;
    values[14] = (jlong)facts.voice_record_stride;
    values[15] = (jlong)facts.voice_meta_base;
    values[16] = (jlong)facts.voice_meta_stride;
    out = (*env)->NewLongArray(env, 17);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 17, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_VoiceDispatchFacts_nativeAll(JNIEnv *env, jclass cls) {
    r6_voice_dispatch_facts_t facts;
    jlong values[32];
    jlongArray out = NULL;
    uint32_t index;
    (void)cls;
    r6_voice_dispatch_facts(&facts);
    for (index = 0; index < 8u; index++) {
        values[index] = (jlong)facts.bank_errors[index];
    }
    for (index = 0; index < 3u; index++) {
        values[8u + index] = (jlong)facts.null_errors[index];
        values[12u + index] = (jlong)facts.chain_modes[index];
    }
    values[11] = (jlong)facts.chain_error;
    for (index = 0; index < 2u; index++) {
        values[15u + index] = (jlong)facts.ext_offsets[index];
        values[17u + index] = (jlong)facts.ext_sizes[index];
    }
    for (index = 0; index < 5u; index++) {
        values[19u + index] = (jlong)facts.game_layout[index];
    }
    for (index = 0; index < 8u; index++) {
        values[24u + index] = (jlong)facts.addresses[index];
    }
    out = (*env)->NewLongArray(env, 32);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 32, values);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_VoiceCoreTableFacts_nativeAll(JNIEnv *env, jclass cls) {
    r6_voice_core_table_facts_t facts;
    jlong values[5];
    jlongArray out = NULL;
    (void)cls;
    r6_voice_core_table_facts(&facts);
    values[0] = (jlong)facts.count;
    values[1] = (jlong)facts.offset;
    values[2] = (jlong)facts.stride;
    values[3] = (jlong)facts.mode;
    values[4] = (jlong)facts.lookup_address;
    out = (*env)->NewLongArray(env, 5);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 5, values);
    }
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_VoiceChain_nativeRead(JNIEnv *env, jclass cls,
                                          jbyteArray data, jint index) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_voice_chain_state state;
    jdouble values[R6_VOICE_CHAIN_FLOATS];
    jdoubleArray out = NULL;
    uint32_t i;
    (void)cls;
    if (raw_from_blob(env, data, &bytes, &length) != R6_OK ||
        r6_voice_chain_read(bytes, length, (uint32_t)index, &state) != R6_OK) {
        free(bytes);
        return NULL;
    }
    for (i = 0; i < R6_VOICE_CHAIN_FLOATS; i++) {
        values[i] = (jdouble)state.values[i];
    }
    out = (*env)->NewDoubleArray(env, R6_VOICE_CHAIN_FLOATS);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, R6_VOICE_CHAIN_FLOATS,
                                     values);
    }
    free(bytes);
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_VoiceChain_nativeWrite(JNIEnv *env, jclass cls,
                                           jbyteArray data, jint index,
                                           jdoubleArray values) {
    unsigned char *bytes = NULL;
    size_t length = 0;
    r6_voice_chain_state state;
    jdouble input[R6_VOICE_CHAIN_FLOATS];
    jbyteArray out = NULL;
    uint32_t i;
    (void)cls;
    if (!values || (*env)->GetArrayLength(env, values) !=
                       R6_VOICE_CHAIN_FLOATS ||
        raw_from_blob(env, data, &bytes, &length) != R6_OK) {
        free(bytes);
        return NULL;
    }
    (*env)->GetDoubleArrayRegion(env, values, 0, R6_VOICE_CHAIN_FLOATS,
                                 input);
    if ((*env)->ExceptionCheck(env)) {
        free(bytes);
        return NULL;
    }
    for (i = 0; i < R6_VOICE_CHAIN_FLOATS; i++) {
        state.values[i] = (float)input[i];
    }
    if (r6_voice_chain_write(bytes, length, (uint32_t)index, &state) !=
        R6_OK) {
        free(bytes);
        return NULL;
    }
    out = (*env)->NewByteArray(env, (jsize)length);
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, (jsize)length,
                                   (const jbyte *)bytes);
    }
    free(bytes);
    return out;
}

JNIEXPORT jbyteArray JNICALL
Java_com_wmmt_re6rr_VoiceChain_nativeApply(JNIEnv *env, jclass cls,
                                           jdoubleArray values) {
    r6_voice_chain_state state;
    r6_envelope_math math_sink = {NULL, engine_pow, engine_exp2};
    unsigned char voice[R6_VOICE_CORE_MIN_SIZE];
    jdouble input[R6_VOICE_CHAIN_FLOATS];
    jbyteArray out = NULL;
    uint32_t i;
    (void)cls;
    if (!values || (*env)->GetArrayLength(env, values) !=
                       R6_VOICE_CHAIN_FLOATS) {
        return NULL;
    }
    (*env)->GetDoubleArrayRegion(env, values, 0, R6_VOICE_CHAIN_FLOATS,
                                 input);
    if ((*env)->ExceptionCheck(env)) {
        return NULL;
    }
    for (i = 0; i < R6_VOICE_CHAIN_FLOATS; i++) {
        state.values[i] = (float)input[i];
    }
    if (r6_voice_chain_apply(&state, voice, sizeof(voice), &math_sink) !=
        R6_OK) {
        return NULL;
    }
    out = (*env)->NewByteArray(env, (jsize)sizeof(voice));
    if (out) {
        (*env)->SetByteArrayRegion(env, out, 0, (jsize)sizeof(voice),
                                   (const jbyte *)voice);
    }
    return out;
}

JNIEXPORT jlongArray JNICALL
Java_com_wmmt_re6rr_StageEffect_nativeHeader(JNIEnv *env, jclass cls,
                                              jbyteArray blob) {
    r6_stage_effect_header header;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jlong values[4];
    jlongArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_stage_effect_parse(bytes, length, &header) != R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jlong)header.version;
    values[1] = (jlong)header.count;
    values[2] = (jlong)header.strings_off;
    values[3] = (jlong)header.strings_size;
    out = (*env)->NewLongArray(env, 4);
    if (out) {
        (*env)->SetLongArrayRegion(env, out, 0, 4, values);
    }
    return out;
}

JNIEXPORT jobjectArray JNICALL
Java_com_wmmt_re6rr_StageEffect_nativeStrings(JNIEnv *env, jclass cls,
                                               jbyteArray blob, jint index) {
    r6_stage_effect_record record;
    unsigned char *bytes = NULL;
    size_t length = 0;
    uint32_t offsets[5];
    jobjectArray out = NULL;
    jclass string_class;
    uint32_t i;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_stage_effect_get(bytes, length, (uint32_t)index, &record) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    offsets[0] = record.set_off;
    offsets[1] = record.symbol_off;
    offsets[2] = record.file_off;
    offsets[3] = record.tone_name_off;
    offsets[4] = record.wav_off;
    string_class = (*env)->FindClass(env, "java/lang/String");
    if (string_class) {
        out = (*env)->NewObjectArray(env, 5, string_class, NULL);
    }
    for (i = 0; out && i < 5; i++) {
        const char *text = r6_stage_effect_string(bytes, length, offsets[i]);
        jstring value = (*env)->NewStringUTF(env, text ? text : "");
        if (value) {
            (*env)->SetObjectArrayElement(env, out, (jsize)i, value);
            (*env)->DeleteLocalRef(env, value);
        }
    }
    free(bytes);
    return out;
}

JNIEXPORT jdoubleArray JNICALL
Java_com_wmmt_re6rr_StageEffect_nativeNumbers(JNIEnv *env, jclass cls,
                                               jbyteArray blob, jint index) {
    r6_stage_effect_record record;
    unsigned char *bytes = NULL;
    size_t length = 0;
    jdouble values[7];
    jdoubleArray out = NULL;
    (void)cls;
    if (raw_from_blob(env, blob, &bytes, &length) != R6_OK ||
        r6_stage_effect_get(bytes, length, (uint32_t)index, &record) !=
            R6_OK) {
        free(bytes);
        return NULL;
    }
    free(bytes);
    values[0] = (jdouble)record.bank;
    values[1] = (jdouble)record.tone;
    values[2] = (jdouble)record.native_tone;
    values[3] = (jdouble)record.loop;
    values[4] = (jdouble)record.x;
    values[5] = (jdouble)record.y;
    values[6] = (jdouble)record.z;
    out = (*env)->NewDoubleArray(env, 7);
    if (out) {
        (*env)->SetDoubleArrayRegion(env, out, 0, 7, values);
    }
    return out;
}

JNIEXPORT jint JNICALL
Java_com_wmmt_re6rr_StageEffect_nativeFind(JNIEnv *env, jclass cls,
                                            jbyteArray blob, jstring symbol) {
    r6_stage_effect_record record;
    unsigned char *bytes = NULL;
    size_t length = 0;
    const char *text = NULL;
    jint result = -1;
    (void)cls;
    if (!symbol) {
        return -1;
    }
    text = (*env)->GetStringUTFChars(env, symbol, NULL);
    if (!text) {
        return -1;
    }
    if (raw_from_blob(env, blob, &bytes, &length) == R6_OK) {
        result = (jint)r6_stage_effect_find_symbol(bytes, length, text,
                                                   &record);
        free(bytes);
    }
    (*env)->ReleaseStringUTFChars(env, symbol, text);
    return result;
}
