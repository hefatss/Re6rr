/* Freestanding inventory of shipped per-car shader Lua numeric parameters.
 * The blob comes from tools/engine/shader_param_catalog.py. Only paths, model
 * names and eight float32 values cross the bridge; no shader binding is
 * inferred. */
#ifndef R6_SHADER_PARAM_CATALOG_H
#define R6_SHADER_PARAM_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_SHADER_PARAM_COUNT 8

typedef struct r6_shader_param_header_t {
    uint32_t version;
    uint32_t count;
    uint32_t string_size;
    uint32_t reserved0;
    uint32_t reserved1;
} r6_shader_param_header_t;

typedef struct r6_shader_param_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t model_offset;
    uint32_t model_length;
    float values[R6_SHADER_PARAM_COUNT];
} r6_shader_param_file_t;

R6_API int r6_shader_param_parse(const void *data, size_t size,
                                 r6_shader_param_header_t *out);

R6_API int r6_shader_param_file(const void *data, size_t size, uint32_t index,
                                r6_shader_param_file_t *out);

/* Copied dump-relative path. */
R6_API int r6_shader_param_path(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

/* Copied model name derived from the Lua filename. */
R6_API int r6_shader_param_model(const void *data, size_t size, uint32_t index,
                                 char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
