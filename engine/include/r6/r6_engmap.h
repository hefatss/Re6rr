/* Freestanding reader for the shipped WM4_ENGMAP text table. No files or CRT;
 * the host supplies the decoded text bytes. */
#ifndef R6_ENGMAP_H
#define R6_ENGMAP_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum { R6_ENGMAP_MAX_PAIRS = 320, R6_ENGMAP_ENTRY_INTS = 20 };

typedef struct r6_engmap_pair_t {
    int32_t engine_sound;
    int32_t group;
} r6_engmap_pair_t;

typedef struct r6_engmap_t {
    uint32_t count;
    r6_engmap_pair_t pairs[R6_ENGMAP_MAX_PAIRS];
} r6_engmap_t;

R6_API int r6_engmap_parse(const void *text, size_t size, r6_engmap_t *out);

#ifdef __cplusplus
}
#endif

#endif
