/* Freestanding reader for the recovered unlock/honor-condition schema. The
 * derived blob comes from tools/engine/honor_schema_catalog.py. No per-episode
 * predicate instances are implied. */
#ifndef R6_HONOR_SCHEMA_H
#define R6_HONOR_SCHEMA_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_HONOR_TYPES = 13,
    R6_HONOR_FIELD_MAX = 5,
    R6_HONOR_NAME_CAP = 0x80
};

typedef struct r6_honor_schema_header {
    uint32_t type_count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_honor_schema_header;

R6_API int r6_honor_schema_parse(const void *data, size_t size,
                                 r6_honor_schema_header *out);

R6_API int r6_honor_schema_type(const void *data, size_t size, uint32_t type,
                                char *name, size_t capacity,
                                uint32_t *field_count);

/* First exact type-name match; R6_ERR_NOT_FOUND means no row matched. */
R6_API int r6_honor_schema_find_type(const void *data, size_t size,
                                     const char *name, uint32_t *index);

R6_API int r6_honor_schema_field(const void *data, size_t size, uint32_t type,
                                 uint32_t field, char *out, size_t capacity);

/* First exact field label in one predicate type. */
R6_API int r6_honor_schema_find_field(const void *data, size_t size,
                                      uint32_t type, const char *name,
                                      uint32_t *index);

/* Verbatim type-1 debug::CheckHonorStoryMode ABI facts from STORY_NATIVE.md.
 * No predicate instance is created and no object is read. */
typedef struct r6_honor_type1_facts_t {
    uint32_t object_size;
    uint32_t clear_episode_offset;
    uint32_t clear_bits_offset;
    uint32_t power_handle_offset;
    uint32_t scratch_offset;
    uint32_t clear_bits_min;
    uint32_t clear_bits_max;
    uint32_t property_offsets[10];
    uint64_t addresses[3];      /* deserializer, constructor, tune helper */
} r6_honor_type1_facts_t;

R6_API void r6_honor_type1_facts(r6_honor_type1_facts_t *out);

#ifdef __cplusplus
}
#endif

#endif
