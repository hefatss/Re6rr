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

/* Zero-fill capacity bytes, then write each value at its reflected offset.
 * On R6_ERR_BUFFER, out_size holds the required capacity. */
R6_API int r6_glsl_pack_ubo(void *ubo, size_t capacity,
                            const r6_glsl_region *regions,
                            const r6_glsl_value *values, size_t count,
                            size_t *out_size);

#ifdef __cplusplus
}
#endif

#endif
