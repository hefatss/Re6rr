/* Packed inventory of story keys hard-coded by wmn6r.exe. The blob is built
 * from the two f_4a3680 / f_4a3730 string uses and the pointer table at
 * RVA 0x12ffd20; names are checked against msgdb.lua. No dialogue, unlock or
 * mission semantics are inferred.
 */
#ifndef R6_STORY_KEYS_H
#define R6_STORY_KEYS_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_STORY_KEYS_HEADER_SIZE 36
#define R6_STORY_KEYS_RECORD_SIZE 16

enum r6_story_key_source {
    R6_STORY_KEY_DIRECT = 1,
    R6_STORY_KEY_TABLE = 2
};

#define R6_STORY_KEY_NO_TABLE 0xFFFFFFFFu

typedef struct r6_story_keys_catalog {
    const unsigned char *rows;
    const char *strings;
    size_t native_count;
    size_t table_count;
    size_t msgdb_count;
    size_t matched_count;
    size_t string_count;
} r6_story_keys_catalog;

/* Validate header, record table and exact size, then return plain views. */
R6_API int r6_story_keys_parse(const void *data, size_t size,
                               r6_story_keys_catalog *out);

/* Copy one NUL-terminated ASCII key into caller storage. */
R6_API int r6_story_keys_name(const r6_story_keys_catalog *catalog,
                              size_t index, char *out, size_t capacity);

/* First exact-match row, or -1 when absent. */
R6_API int r6_story_keys_find(const r6_story_keys_catalog *catalog,
                              const char *name);

/* source and table index; direct rows carry R6_STORY_KEY_NO_TABLE. */
R6_API int r6_story_keys_fact(const r6_story_keys_catalog *catalog,
                              size_t index, uint32_t *source,
                              uint32_t *table_index);

#ifdef __cplusplus
}
#endif

#endif
