/* Freestanding reader for shipped SHDR usage maps packed from cbuffer and
 * texture/sampler operands. The blob comes from
 * tools/engine/shader_usage_catalog.py. Keys are reflected names, not
 * translated shader behaviour. */
#ifndef R6_SHADER_USAGE_H
#define R6_SHADER_USAGE_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_SHADER_USAGE_STAGE_VERTEX = 0,
    R6_SHADER_USAGE_STAGE_PIXEL = 1,
    R6_SHADER_USAGE_NAME_CAP = 0x80
};

typedef struct r6_shader_usage_header {
    uint32_t version;
    uint32_t record_count;
    uint32_t uniform_count;
    uint32_t resource_count;
    uint32_t declared_count;
    uint32_t record_off;
    uint32_t uniform_off;
    uint32_t resource_off;
    uint32_t declared_off;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_shader_usage_header;

typedef struct r6_shader_usage_record_t {
    uint32_t name_off;
    uint32_t stage;
    uint32_t uniform_first;
    uint32_t uniform_count;
    uint32_t dynamic_cbuffer;
    uint32_t resource_first;
    uint32_t resource_count;
    uint32_t declared_first;
    uint32_t declared_count;
    uint32_t dynamic_resource;
    uint32_t unmapped_resource;
} r6_shader_usage_record_t;

typedef struct r6_shader_usage_named_t {
    uint32_t name_off;
    uint32_t count;
} r6_shader_usage_named_t;

R6_API int r6_shader_usage_parse(const void *data, size_t size,
                                 r6_shader_usage_header *out);

R6_API int r6_shader_usage_record(const void *data, size_t size,
                                  uint32_t index,
                                  r6_shader_usage_record_t *out);

R6_API int r6_shader_usage_name(const void *data, size_t size, uint32_t index,
                                char *name, size_t capacity);

R6_API int r6_shader_usage_find(const void *data, size_t size,
                                const char *name, uint32_t stage,
                                uint32_t *index);

R6_API int r6_shader_usage_uniform(const void *data, size_t size,
                                   uint32_t record, uint32_t index,
                                   char *name, size_t capacity,
                                   uint32_t *count);

R6_API int r6_shader_usage_find_uniform(const void *data, size_t size,
                                        uint32_t record, const char *name,
                                        uint32_t *index, uint32_t *count);

R6_API int r6_shader_usage_resource(const void *data, size_t size,
                                    uint32_t record, uint32_t index,
                                    char *name, size_t capacity,
                                    uint32_t *count);

R6_API int r6_shader_usage_find_resource(const void *data, size_t size,
                                         uint32_t record, const char *name,
                                         uint32_t *index, uint32_t *count);

R6_API int r6_shader_usage_declared(const void *data, size_t size,
                                    uint32_t record, uint32_t index,
                                    char *name, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
