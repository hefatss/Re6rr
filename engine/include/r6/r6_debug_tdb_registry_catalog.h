/* Freestanding inventory of shipped course-debug TDB id/name rows. The blob
 * comes from tools/engine/debug_tdb_registry_catalog.py. Ids, decimal comments,
 * ASCII names, blink names and accessor names are copied; no rendering or
 * gameplay meaning is inferred. */
#ifndef R6_DEBUG_TDB_REGISTRY_CATALOG_H
#define R6_DEBUG_TDB_REGISTRY_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_debug_tdb_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t pair_count;
    uint32_t string_size;
    uint32_t table_bytes;
    uint32_t accessor_count;
    uint32_t accessor_size;
    uint32_t blink_count;
    uint32_t blink_size;
} r6_debug_tdb_header_t;

typedef struct r6_debug_tdb_file_t {
    uint32_t path_offset;
    uint32_t path_length;
    uint32_t size;
    uint32_t pairs;
} r6_debug_tdb_file_t;

typedef struct r6_debug_tdb_pair_t {
    uint32_t id;
    uint32_t decimal;
    uint32_t name_offset;
    uint32_t name_length;
} r6_debug_tdb_pair_t;

R6_API int r6_debug_tdb_parse(const void *data, size_t size,
                              r6_debug_tdb_header_t *out);

R6_API int r6_debug_tdb_file(const void *data, size_t size, uint32_t index,
                             r6_debug_tdb_file_t *out);

R6_API int r6_debug_tdb_path(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_debug_tdb_pair(const void *data, size_t size, uint32_t index,
                             r6_debug_tdb_pair_t *out);

R6_API int r6_debug_tdb_blink(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity);

R6_API int r6_debug_tdb_accessor(const void *data, size_t size,
                                 uint32_t index, char *out, size_t capacity);

#ifdef __cplusplus
}
#endif

#endif
