/* Freestanding inventory of root FBK/GBK_W6W gzip bank records. The blob comes
 * from tools/engine/wmbk_bank_catalog.py. Paths, gzip header words and WMBK
 * record headers are copied; payload u32 words are not decoded. */
#ifndef R6_WMBK_BANK_CATALOG_H
#define R6_WMBK_BANK_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_wmbk_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t record_count;
    uint32_t string_size;
    uint32_t compressed_total;
    uint32_t inflated_total;
} r6_wmbk_header_t;

typedef struct r6_wmbk_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t compressed;
    uint32_t inflated;
    uint32_t mtime;
    uint32_t isize;
    uint32_t record_first;
    uint32_t record_count;
    uint32_t flg;
    uint32_t xfl;
    uint32_t os;
} r6_wmbk_file_t;

typedef struct r6_wmbk_record_t {
    uint32_t file_index;
    uint32_t byte_offset;
    uint32_t magic;
    uint32_t version;
    uint32_t payload_length;
} r6_wmbk_record_t;

R6_API int r6_wmbk_bank_parse(const void *data, size_t size,
                              r6_wmbk_header_t *out);

R6_API int r6_wmbk_bank_file(const void *data, size_t size, uint32_t index,
                             r6_wmbk_file_t *out);

R6_API int r6_wmbk_bank_path(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_wmbk_bank_record(const void *data, size_t size, uint32_t index,
                               r6_wmbk_record_t *out);

#ifdef __cplusplus
}
#endif

#endif
