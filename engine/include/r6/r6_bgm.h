/* Reader for the packed shipped BGM id/name/path table.
 *
 * Rows are recovered from wmn6r.exe by tools/engine/audio_events.py and packed
 * by tools/engine/bgm_catalog.py. The core validates offsets and returns copies
 * of fixed records; names and paths stay in the caller-owned blob. No files,
 * allocation, CRT or libm.
 */
#ifndef R6_BGM_H
#define R6_BGM_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_BGM_HEADER_SIZE 32u
#define R6_BGM_RECORD_SIZE 12u

enum {
    R6_BGM_FLAG_STOP = 0x0001,
    R6_BGM_FLAG_RANDOM = 0x0002
};

typedef struct r6_bgm_header {
    uint32_t version;
    uint32_t count;
    uint32_t id_first;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_bgm_header;

typedef struct r6_bgm_record {
    uint16_t id;
    uint16_t flags;
    uint32_t name_off;
    uint32_t path_off;
} r6_bgm_record;

R6_API int r6_bgm_parse(const void *data, size_t size, r6_bgm_header *out);

/* Direct lookup by shipped id; ids are contiguous from id_first. */
R6_API int r6_bgm_find_id(const void *data, size_t size, uint16_t id,
                          r6_bgm_record *out);

/* Substring lookup by name, matching audio_events.bgm_by_name(). */
R6_API int r6_bgm_find_name(const void *data, size_t size, const char *name,
                            r6_bgm_record *out);

/* NUL-terminated interned name or path, or NULL outside the string table. */
R6_API const char *r6_bgm_string(const void *data, size_t size,
                                 uint32_t offset);

#ifdef __cplusplus
}
#endif

#endif
