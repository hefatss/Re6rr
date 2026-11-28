/* Freestanding inventory of shipped ytCarryover.txt tokens.
 * The blob comes from tools/engine/carryover_catalog.py. Series token, five
 * scalar lines and four fixed data rows are copied verbatim. Carryover rules,
 * checkpoint tokens, coordinates and float semantics are not decoded. */
#ifndef R6_CARRYOVER_CATALOG_H
#define R6_CARRYOVER_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_carryover_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t record_count;
    uint32_t row_count;
    uint32_t string_size;
    uint32_t source_bytes;
} r6_carryover_header_t;

typedef struct r6_carryover_record_t {
    uint32_t text_offset;
    uint32_t text_length;
    uint32_t kind;
    uint32_t line;
} r6_carryover_record_t;

typedef struct r6_carryover_row_t {
    uint32_t bool_offset;
    uint32_t bool_length;
    uint32_t number_offset;
    uint32_t number_length;
    uint32_t token_offset;
    uint32_t token_length;
    uint32_t first_offset;
    uint32_t first_length;
    uint32_t second_offset;
    uint32_t second_length;
    uint32_t third_offset;
    uint32_t third_length;
    uint32_t tail_offset;
    uint32_t tail_length;
    uint32_t line;
} r6_carryover_row_t;

R6_API int r6_carryover_parse(const void *data, size_t size,
                              r6_carryover_header_t *out);

R6_API int r6_carryover_record(const void *data, size_t size, uint32_t index,
                               r6_carryover_record_t *out);

R6_API int r6_carryover_text(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_carryover_row(const void *data, size_t size, uint32_t index,
                            r6_carryover_row_t *out);

R6_API int r6_carryover_field(const void *data, size_t size, uint32_t index,
                              uint32_t field, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
