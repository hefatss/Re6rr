/* Freestanding inventory of PLC_MA61_Specification.lua scalar rows.
 * The blob comes from tools/engine/spec_ma61_catalog.py. Path, table span,
 * key names, ASCII scalar literals and comment presence are copied. Physics
 * meaning, message-ID resolution, Japanese literals/comments and accessor
 * bodies stay unparsed. */
#ifndef R6_SPEC_MA61_CATALOG_H
#define R6_SPEC_MA61_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_spec_ma61_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t lines;
    uint32_t table_start;
    uint32_t table_end;
    uint32_t path_offset;
    uint32_t path_length;
} r6_spec_ma61_header_t;

typedef struct r6_spec_ma61_row_t {
    uint32_t key_offset;
    uint32_t key_length;
    uint32_t literal_offset;
    uint32_t literal_length;
    uint32_t kind;
    uint32_t line;
    uint32_t comment;
} r6_spec_ma61_row_t;

R6_API int r6_spec_ma61_parse(const void *data, size_t size,
                              r6_spec_ma61_header_t *out);

R6_API int r6_spec_ma61_path(const void *data, size_t size, char *out,
                             size_t capacity);

R6_API int r6_spec_ma61_row(const void *data, size_t size, uint32_t index,
                            r6_spec_ma61_row_t *out);

R6_API int r6_spec_ma61_key(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity);

R6_API int r6_spec_ma61_literal(const void *data, size_t size, uint32_t index,
                                char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
