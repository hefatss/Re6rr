/* Re6rr engine core.
 *
 * The core is data-driven and freestanding: the host owns memory and feeds
 * bytes in. The Android platform layer will read the dump; the host tests feed
 * the same bytes from Python.
 */
#ifndef R6_H
#define R6_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) && defined(R6_BUILD_DLL)
#define R6_API __declspec(dllexport)
#elif defined(__GNUC__)
#define R6_API __attribute__((visibility("default")))
#else
#define R6_API
#endif

enum {
    R6_OK = 0,
    R6_ERR_ARG = -1,
    R6_ERR_MEMORY = -2,
    R6_ERR_LUA = -3,
    R6_ERR_SCRIPT = -4,
    R6_ERR_FORMAT = -5,
    R6_ERR_BUFFER = -6,
    R6_ERR_NOT_FOUND = -7
};

typedef struct r6_engine r6_engine;

typedef void (*r6_log_fn)(void *user, int level, const char *message, size_t len);

typedef struct r6_config {
    r6_log_fn log;
    void *log_user;
    void *arena;       /* caller-owned scratch memory, optional */
    size_t arena_size;
} r6_config;

/* Size of the opaque engine object. The host allocates this storage. */
R6_API size_t r6_engine_size(void);
R6_API r6_engine *r6_engine_init(void *storage, size_t size, const r6_config *config);
R6_API void r6_engine_shutdown(r6_engine *engine);

/* Load a plain Lua chunk. Gzip/BOM handling belongs to the platform layer. */
R6_API int r6_engine_load_script(r6_engine *engine, const char *chunk_name,
                                 const void *data, size_t size);
R6_API int r6_engine_set_number(r6_engine *engine, const char *name, double value);
R6_API int r6_engine_set_setting_const(r6_engine *engine);
R6_API int r6_engine_has_function(r6_engine *engine, const char *name);

/* Native -> Lua calls, matching wmn6r.exe FUN_1400ffb60/FUN_1400d20d0.
 * On failure the native code yields a zero vector or zero scalar, and so do
 * these: `out` is zeroed before the call and stays zero when the call fails. */
R6_API int r6_engine_call_vec3_key(r6_engine *engine, const char *name,
                                   const char *key, int index, float out[3]);
R6_API int r6_engine_call_vec3_index(r6_engine *engine, const char *name,
                                     int index, float out[3]);
R6_API int r6_engine_call_number(r6_engine *engine, const char *name, double *out);

/* One ordered script of a context bundle. */
typedef struct r6_script_source {
    const char *name;  /* chunk name used in Lua errors, may be NULL */
    const void *data;
    size_t size;
} r6_script_source;

/* Load a context bundle in order and stop at the first failure.
 *
 * The real engine loads one context at a time: the data scripts overwrite
 * globals such as ColorMax and GetTirePos, so the caller must pass the exact
 * set for the car, colour or course currently in use. Loading is sequential and
 * a failed script leaves the state at the scripts before it. */
R6_API int r6_engine_load_context(r6_engine *engine,
                                  const r6_script_source *scripts,
                                  size_t count);

/* Last error string is NUL-terminated and copied into buf. */
R6_API int r6_engine_last_error(const r6_engine *engine, char *buf, size_t cap);

#ifdef __cplusplus
}
#endif

#endif
