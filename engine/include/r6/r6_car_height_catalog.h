/* Freestanding inventory of shipped car height and aero offset rows.
 * The blob comes from tools/engine/car_height_catalog.py. Paths, row positions,
 * aero slot labels and verbatim numeric token bytes are copied. CP932 comments
 * and ride-height/aero semantics stay unparsed. */
#ifndef R6_CAR_HEIGHT_CATALOG_H
#define R6_CAR_HEIGHT_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_chg_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t token_count;
    uint32_t line_count;
    uint32_t height_rows;
    uint32_t aero_rows;
    uint32_t source_bytes;
    uint32_t string_size;
    uint32_t reserved;
} r6_chg_header_t;

typedef struct r6_chg_file_t {
    uint32_t name_offset;
    uint32_t name_length;
    uint32_t size;
    uint32_t row_base;
} r6_chg_file_t;

typedef struct r6_chg_row_t {
    uint32_t line;
    uint32_t token0_offset;
    uint32_t token1_offset;
    uint32_t label_offset;
    uint32_t label_length;
} r6_chg_row_t;

R6_API int r6_chg_parse(const void *data, size_t size, r6_chg_header_t *out);

R6_API int r6_chg_file(const void *data, size_t size, uint32_t index,
                       r6_chg_file_t *out);

R6_API int r6_chg_name(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity);

R6_API int r6_chg_row(const void *data, size_t size, uint32_t index,
                      r6_chg_row_t *out);

R6_API int r6_chg_token(const void *data, size_t size, uint32_t index,
                        uint32_t slot, char *out, size_t capacity);

R6_API int r6_chg_label(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
