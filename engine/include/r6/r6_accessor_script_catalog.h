/* Freestanding inventory of shipped Lua accessor script functions.
 * The blob comes from tools/engine/accessor_script_catalog.py. Paths,
 * function names, argument lists, first return expressions and line positions
 * are copied. CP932 comments, unpack semantics and render/tuning behavior are
 * not decoded. */
#ifndef R6_ACCESSOR_SCRIPT_CATALOG_H
#define R6_ACCESSOR_SCRIPT_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_accessor_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t function_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_accessor_header_t;

typedef struct r6_accessor_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t lines;
    uint32_t function_base;
    uint32_t count;
    uint32_t returns;
} r6_accessor_file_t;

typedef struct r6_accessor_func_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t args_offset;
    uint32_t args_length;
    uint32_t result_offset;
    uint32_t result_length;
    uint32_t line;
} r6_accessor_func_t;

R6_API int r6_accessor_parse(const void *data, size_t size,
                             r6_accessor_header_t *out);

R6_API int r6_accessor_file(const void *data, size_t size, uint32_t index,
                            r6_accessor_file_t *out);

R6_API int r6_accessor_path(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_accessor_func(const void *data, size_t size, uint32_t index,
                            r6_accessor_func_t *out);

R6_API int r6_accessor_name(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_accessor_args(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_accessor_result(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
