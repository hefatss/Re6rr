/* Freestanding inventory of shipped filter Lua line shapes. The blob comes
 * from tools/engine/filter_dictionary_catalog.py. Line kinds, byte spans and
 * true/false tokens are copied; dictionary word values are not copied. */
#ifndef R6_FILTER_DICTIONARY_CATALOG_H
#define R6_FILTER_DICTIONARY_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_FILTER_KIND_TABLE = 0,
    R6_FILTER_KIND_OPEN = 1,
    R6_FILTER_KIND_CLOSE = 2,
    R6_FILTER_KIND_ACTIVE = 3,
    R6_FILTER_KIND_COMMENTED = 4,
    R6_FILTER_KIND_BOOL = 5,
    R6_FILTER_KIND_FUNCTION = 6
};

typedef struct r6_filter_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_bytes;
    uint32_t source_lines;
} r6_filter_header_t;

typedef struct r6_filter_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t source_size;
    uint32_t line_count;
    uint32_t active;
    uint32_t commented;
    uint32_t bool_count;
    uint32_t table;
    uint32_t function;
    uint32_t row_first;
    uint32_t row_count;
} r6_filter_file_t;

typedef struct r6_filter_row_t {
    uint32_t file_index;
    uint32_t line_index;
    uint32_t byte_offset;
    uint32_t line_length;
    uint32_t kind;
    uint32_t value;
} r6_filter_row_t;

R6_API int r6_filter_dictionary_parse(const void *data, size_t size,
                                      r6_filter_header_t *out);

R6_API int r6_filter_dictionary_file(const void *data, size_t size,
                                     uint32_t index, r6_filter_file_t *out);

R6_API int r6_filter_dictionary_path(const void *data, size_t size,
                                     uint32_t index, char *out,
                                     size_t capacity);

R6_API int r6_filter_dictionary_row(const void *data, size_t size,
                                    uint32_t index, r6_filter_row_t *out);

#ifdef __cplusplus
}
#endif

#endif
