/* Freestanding reader for the shipped config_3d.bin used by nuSound2.
 *
 * Layout and field arithmetic come from `tools/engine/audio_events.py`
 * (FUN_180032520). The view points into caller-owned bytes and caller-owned
 * section storage: no allocation, files, CRT, libm or audio device.
 */
#ifndef R6_CONFIG_3D_H
#define R6_CONFIG_3D_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"
#include "r6_envelope.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_CONFIG_3D_HEADER_SIZE = 0x20,
    R6_CONFIG_3D_SECTION_STRIDE = 0x130,
    R6_CONFIG_3D_RECORD_STRIDE = 0x1C,
    R6_CONFIG_3D_RECORD_COUNT = 10,
    R6_CONFIG_3D_TAIL_OFFSET = 0x118,
    R6_CONFIG_3D_TAIL_COUNT = 6,
    R6_CONFIG_3D_SECTION_MAX = 0x20
};

#define R6_CONFIG_3D_DB_TO_AMPLITUDE_SCALE 0.115129255

typedef struct r6_config_3d_record {
    uint32_t flags;
    float db_start;
    float angle;
    float db_end;
    uint32_t raw[3];
} r6_config_3d_record;

typedef struct r6_config_3d_section {
    r6_config_3d_record records[R6_CONFIG_3D_RECORD_COUNT];
    uint32_t tail[R6_CONFIG_3D_TAIL_COUNT];
} r6_config_3d_section;

typedef struct r6_config_3d_view {
    unsigned char version[3];
    uint32_t count;
    uint32_t stride;
    float floats[4];
    const r6_config_3d_section *sections;
} r6_config_3d_view;

/* `sections` must hold at least `capacity` records of section storage. */
R6_API int r6_config_3d_init(r6_config_3d_view *view, const void *data,
                             size_t size, r6_config_3d_section *sections,
                             uint32_t capacity);

/* FUN_1800274d0: 10^(db * ln(10)/20) above the zero-dB floor; pow from host. */
R6_API int r6_config_3d_amplitude(const r6_envelope_math *math, double db,
                                  double zero_db, double *out);

#ifdef __cplusplus
}
#endif

#endif
