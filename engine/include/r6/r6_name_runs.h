/* Freestanding reader for shipped string-pointer runs found in wmn6r.exe.
 * The derived blob comes from tools/engine/name_runs_catalog.py. RVAs are
 * reported as data; no pointer table is dereferenced by the core. */
#ifndef R6_NAME_RUNS_H
#define R6_NAME_RUNS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_NAME_RUNS_RUNS = 521,
    R6_NAME_RUNS_NAMES = 13283,
    R6_NAME_RUNS_USERS = 888,
    R6_NAME_RUNS_NAME_CAP = 256
};

typedef struct r6_name_runs_header {
    uint32_t version;
    uint32_t run_count;
    uint32_t name_count;
    uint32_t user_count;
    uint32_t strings_size;
} r6_name_runs_header;

R6_API int r6_name_runs_parse(const void *data, size_t size,
                              r6_name_runs_header *out);

R6_API int r6_name_runs_run(const void *data, size_t size, uint32_t index,
                            uint32_t *rva, uint32_t *table_size,
                            uint32_t *stride, uint32_t *count,
                            uint32_t *name_first, uint32_t *user_first,
                            uint32_t *user_count);

R6_API int r6_name_runs_name(const void *data, size_t size, uint32_t index,
                             char *out, size_t capacity);

R6_API int r6_name_runs_run_name(const void *data, size_t size,
                                 uint32_t run_index, uint32_t local_index,
                                 char *out, size_t capacity);

R6_API int r6_name_runs_user(const void *data, size_t size, uint32_t index,
                             uint32_t *rva);

/* Linear search over the shipped names. On success returns run, local and
 * global indexes; R6_ERR_NOT_FOUND means no name matched. */
R6_API int r6_name_runs_find(const void *data, size_t size, const char *name,
                             uint32_t *run_index, uint32_t *local_index,
                             uint32_t *global_index);

/* First code-reference row with the exact RVA. */
R6_API int r6_name_runs_find_user(const void *data, size_t size, uint32_t rva,
                                  uint32_t *index);

/* All code-reference rows with that exact RVA, in stored order. *count gets
 * the total; up to capacity indexes are copied. R6_ERR_NOT_FOUND means none,
 * R6_ERR_BUFFER means the capacity was short. */
R6_API int r6_name_runs_find_user_rva(const void *data, size_t size,
                                      uint32_t rva, uint32_t *indices,
                                      uint32_t capacity, uint32_t *count);

#ifdef __cplusplus
}
#endif

#endif
