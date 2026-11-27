/* Freestanding reader for structured SM4 control-flow blocks packed from the
 * shipped NSXR SHDR streams. The blob comes from
 * tools/engine/shader_control_flow_catalog.py. No branch targets are invented
 * and no shader bytecode is executed. */
#ifndef R6_SHADER_CF_H
#define R6_SHADER_CF_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_SHADER_CF_STAGE_VERTEX = 0,
    R6_SHADER_CF_STAGE_PIXEL = 1,
    R6_SHADER_CF_NAME_CAP = 0x80,
    R6_SHADER_CF_IF = 0,
    R6_SHADER_CF_LOOP = 1,
    R6_SHADER_CF_SWITCH = 2,
    R6_SHADER_CF_CASE = 0,
    R6_SHADER_CF_DEFAULT = 1,
    R6_SHADER_CF_NO_ELSE = 0xFFFFFFFFu
};

typedef struct r6_shader_cf_header {
    uint32_t version;
    uint32_t record_count;
    uint32_t block_count;
    uint32_t case_count;
    uint32_t index_count;
    uint32_t records_off;
    uint32_t blocks_off;
    uint32_t cases_off;
    uint32_t indices_off;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_shader_cf_header;

typedef struct r6_shader_cf_record_t {
    uint32_t name_off;
    uint32_t stage;
    uint32_t first_block;
    uint32_t block_count;
    uint32_t unmatched_first;
    uint32_t unmatched_count;
} r6_shader_cf_record_t;

typedef struct r6_shader_cf_block_t {
    uint32_t kind;
    uint32_t start;
    uint32_t end;
    uint32_t else_index;
    uint32_t case_first;
    uint32_t case_count;
    uint32_t break_first;
    uint32_t break_count;
    uint32_t continue_first;
    uint32_t continue_count;
} r6_shader_cf_block_t;

typedef struct r6_shader_cf_case_t {
    uint32_t kind;
    uint32_t start;
} r6_shader_cf_case_t;

R6_API int r6_shader_cf_parse(const void *data, size_t size,
                              r6_shader_cf_header *out);

R6_API int r6_shader_cf_record(const void *data, size_t size, uint32_t index,
                               r6_shader_cf_record_t *out);

R6_API int r6_shader_cf_name(const void *data, size_t size, uint32_t index,
                             char *name, size_t capacity);

R6_API int r6_shader_cf_find(const void *data, size_t size, const char *name,
                             uint32_t stage, uint32_t *index);

R6_API int r6_shader_cf_block(const void *data, size_t size, uint32_t index,
                              r6_shader_cf_block_t *out);

R6_API int r6_shader_cf_case(const void *data, size_t size, uint32_t index,
                             r6_shader_cf_case_t *out);

/* One break, continue or unmatched instruction index. */
R6_API int r6_shader_cf_index(const void *data, size_t size, uint32_t index,
                              uint32_t *out);

#ifdef __cplusplus
}
#endif

#endif
