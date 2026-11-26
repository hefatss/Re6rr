/* std140 UBO packing for the GLSL ES emitter. The core only writes bytes:
 * the caller supplies reflected member offsets from the shader export and owns
 * both the UBO buffer and the values. No files, allocation, CRT or libm. */
#ifndef R6_GLSL_H
#define R6_GLSL_H

#include <stddef.h>
#include <stdint.h>

#include "r6.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    R6_GLSL_SCALAR = 0,
    R6_GLSL_VECTOR = 1,
    R6_GLSL_MATRIX = 2,
    R6_GLSL_FLOAT = 0,
    R6_GLSL_UINT = 1
};

typedef struct r6_glsl_region {
    uint32_t offset;
    uint32_t size;
    uint8_t kind;
    uint8_t type;
} r6_glsl_region;

typedef union r6_glsl_value {
    float f;
    uint32_t u;
    float v[4];
    float m[16];
} r6_glsl_value;

/* Description of one decoded RGBA8 texture upload to a GLES sampler unit.
 * Enums are numeric GL values so the freestanding core needs no GL headers. */
typedef struct r6_glsl_texture_desc {
    uint32_t unit;
    uint32_t internal_format;
    uint32_t format;
    uint32_t type;
    uint32_t width;
    uint32_t height;
    uint32_t size;
} r6_glsl_texture_desc;

/* Zero-fill capacity bytes, then write each value at its reflected offset.
 * On R6_ERR_BUFFER, out_size holds the required capacity. */
R6_API int r6_glsl_pack_ubo(void *ubo, size_t capacity,
                            const r6_glsl_region *regions,
                            const r6_glsl_value *values, size_t count,
                            size_t *out_size);

/* Describe a decoded RGBA8 upload for one .nut format and sampler unit.
 * R6_ERR_BUFFER means the RGBA8 byte count does not fit in uint32_t. */
R6_API int r6_glsl_texture_upload(uint32_t unit, uint8_t nut_format,
                                  uint32_t width, uint32_t height,
                                  r6_glsl_texture_desc *out);

#ifdef __cplusplus
}
#endif

#endif
