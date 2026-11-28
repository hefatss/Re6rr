/* Freestanding inventory of the shipped ytPhantomTempRun.bin binary shape.
 * The blob comes from tools/engine/phantom_run_catalog.py. Six header words,
 * five u64 timestamps and 2,333 u64 records are copied verbatim. No timestamp
 * unit, record flag, count meaning or sample encoding is inferred. */
#ifndef R6_PHANTOM_RUN_CATALOG_H
#define R6_PHANTOM_RUN_CATALOG_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct r6_phantom_header_t {
    uint32_t version;
    uint32_t file_count;
    uint32_t record_count;
    uint32_t timestamp_count;
    uint32_t source_bytes;
    uint32_t words[6];
} r6_phantom_header_t;

R6_API int r6_phantom_parse(const void *data, size_t size,
                            r6_phantom_header_t *out);

R6_API int r6_phantom_timestamp(const void *data, size_t size, uint32_t index,
                                uint64_t *out);

R6_API int r6_phantom_record(const void *data, size_t size, uint32_t index,
                             uint64_t *out);

#ifdef __cplusplus
}
#endif

#endif
