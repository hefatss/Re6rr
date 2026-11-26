/* Reader for the packed shipped stage-effect symbolic sound rows.
 *
 * Rows are recovered from FUN_1401b0cd0 and the three shipped parameter
 * scripts by tools/engine/stage_effect_sound.py and packed by
 * stage_effect_catalog.py. The core validates offsets and returns fixed
 * records; strings stay in the caller-owned blob. No files, CRT or libm.
 */
#ifndef R6_STAGE_EFFECT_H
#define R6_STAGE_EFFECT_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_STAGE_EFFECT_HEADER_SIZE 32u
#define R6_STAGE_EFFECT_RECORD_SIZE 40u

typedef struct r6_stage_effect_header {
    uint32_t version;
    uint32_t count;
    uint32_t strings_off;
    uint32_t strings_size;
} r6_stage_effect_header;

typedef struct r6_stage_effect_record {
    uint32_t set_off;
    uint32_t symbol_off;
    uint32_t file_off;
    uint32_t tone_name_off;
    uint32_t wav_off;
    uint16_t bank;
    uint16_t tone;
    uint16_t native_tone;
    uint16_t loop;
    float x;
    float y;
    float z;
} r6_stage_effect_record;

R6_API int r6_stage_effect_parse(const void *data, size_t size,
                                 r6_stage_effect_header *out);
R6_API int r6_stage_effect_get(const void *data, size_t size, uint32_t index,
                               r6_stage_effect_record *out);
R6_API int r6_stage_effect_find_symbol(const void *data, size_t size,
                                       const char *symbol,
                                       r6_stage_effect_record *out);

/* Interned, NUL-terminated string, or NULL outside the string table. */
R6_API const char *r6_stage_effect_string(const void *data, size_t size,
                                          uint32_t offset);

#ifdef __cplusplus
}
#endif

#endif
