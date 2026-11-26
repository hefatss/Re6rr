/* Freestanding reader for shipped .pdata statistics. The derived blob comes
 * from tools/engine/pdata_stats_catalog.py; RVAs are copied, not resolved. */
#ifndef R6_PDATA_STATS_H
#define R6_PDATA_STATS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_PDATA_BUCKETS = 7,
    R6_PDATA_LARGEST = 20,
    R6_PDATA_STATS_NAME_CAP = 32
};

typedef struct r6_pdata_stats_header {
    uint32_t version;
    uint32_t function_count;
    uint32_t code_bytes;
    uint32_t text_bytes;
    uint32_t leaf;
    uint32_t chained;
    uint32_t with_eh;
    uint32_t min_size;
    uint32_t max_size;
    uint32_t median;
    uint32_t bucket_count;
    uint32_t largest_count;
    uint32_t strings_size;
    uint32_t strings_off;
} r6_pdata_stats_header;

R6_API int r6_pdata_stats_parse(const void *data, size_t size,
                                r6_pdata_stats_header *out);

R6_API int r6_pdata_stats_bucket(const void *data, size_t size,
                                 uint32_t index, char *label,
                                 size_t capacity, uint32_t *count);

R6_API int r6_pdata_stats_largest(const void *data, size_t size,
                                  uint32_t index, uint32_t *begin,
                                  uint32_t *end, uint32_t *func_size,
                                  uint32_t *unwind_rva, uint32_t *flags,
                                  uint32_t *leaf, uint32_t *chain_begin,
                                  uint32_t *chain_end, uint32_t *chain_unwind,
                                  char *section, size_t capacity);

/* Exact begin-RVA match; R6_ERR_NOT_FOUND means no largest row matched. */
R6_API int r6_pdata_stats_find(const void *data, size_t size, uint32_t begin,
                               uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
