/* Freestanding reader for the shipped EMTIS numeric section table. No CRT,
 * files or libm: the host supplies text bytes and this reports section bounds,
 * the first eight tokens of each section, prefix name counts and copied
 * source WAV names. */
#ifndef R6_EMTIS_H
#define R6_EMTIS_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_EMTIS_VERSION_MAX = 8,
    R6_EMTIS_HEADER_MAX = 64,
    R6_EMTIS_SECTION_MAX = 16,
    R6_EMTIS_SECTION_HEAD = 8,
    R6_EMTIS_NAME_PREFIXES = 4
};

typedef struct r6_emtis_section_t {
    int32_t marker;
    int32_t start;
    int32_t length;
    double head[R6_EMTIS_SECTION_HEAD];
} r6_emtis_section_t;

typedef struct r6_emtis_t {
    uint32_t version[R6_EMTIS_VERSION_MAX];
    uint32_t version_count;
    double header[R6_EMTIS_HEADER_MAX];
    uint32_t header_count;
    uint32_t token_count;
    r6_emtis_section_t sections[R6_EMTIS_SECTION_MAX];
    uint32_t section_count;
    uint32_t name_count;
    uint32_t name_counts[R6_EMTIS_NAME_PREFIXES];
} r6_emtis_t;

R6_API int r6_emtis_parse(const void *text, size_t size, r6_emtis_t *out);

/* Copy one name line after the four numeric header lines. */
R6_API int r6_emtis_name(const void *text, size_t size, uint32_t index,
                         char *name, size_t capacity);

/* First exact name line; R6_ERR_NOT_FOUND means no line matched. */
R6_API int r6_emtis_find_name(const void *text, size_t size,
                              const char *name, uint32_t *index);

#ifdef __cplusplus
}
#endif

#endif
