/* Freestanding inventory of shipped tire/lamp/strobo position row shapes.
 * The blob comes from tools/engine/tire_lamp_pos_catalog.py. Paths, embedded
 * car ids, section keys and lines, scalar count tokens and verbatim vector
 * token bytes are copied. CP932 comments, axis meanings and lighting roles
 * stay unparsed. */
#ifndef R6_TIRE_LAMP_POS_CATALOG_H
#define R6_TIRE_LAMP_POS_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_tlp_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t section_count;
    uint32_t list_count;
    uint32_t scalar_count;
    uint32_t row_count;
    uint32_t token_count;
    uint32_t line_count;
    uint32_t source_bytes;
    uint32_t string_size;
    uint32_t reserved;
} r6_tlp_header_t;

typedef struct r6_tlp_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t car_id_offset;
    uint32_t car_id_length;
    uint32_t size;
    uint32_t lines;
    uint32_t section_base;
    uint32_t section_count;
} r6_tlp_file_t;

typedef struct r6_tlp_section_t {
    uint32_t key_offset;
    uint32_t key_length;
    uint32_t line;
    uint32_t kind;
    uint32_t value_offset;
    uint32_t value_length;
    uint32_t row_base;
    uint32_t row_count;
} r6_tlp_section_t;

typedef struct r6_tlp_row_t {
    uint32_t line;
    uint32_t token0_offset;
    uint32_t token1_offset;
    uint32_t token2_offset;
} r6_tlp_row_t;

R6_API int r6_tlp_parse(const void *data, size_t size, r6_tlp_header_t *out);

R6_API int r6_tlp_file(const void *data, size_t size, uint32_t index,
                       r6_tlp_file_t *out);

R6_API int r6_tlp_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_tlp_car_id(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity);

R6_API int r6_tlp_section(const void *data, size_t size, uint32_t index,
                          r6_tlp_section_t *out);

R6_API int r6_tlp_key(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity);

R6_API int r6_tlp_value(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

R6_API int r6_tlp_row(const void *data, size_t size, uint32_t index,
                      r6_tlp_row_t *out);

R6_API int r6_tlp_token(const void *data, size_t size, uint32_t index,
                        uint32_t slot, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
