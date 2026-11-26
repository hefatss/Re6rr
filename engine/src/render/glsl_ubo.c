#include "r6/r6_glsl.h"

#include "core/internal.h"

/* Explicit little-endian writes keep the buffer identical on host and device. */
static void r6_glsl_put_u32(unsigned char *out, uint32_t value) {
    out[0] = (unsigned char)value;
    out[1] = (unsigned char)(value >> 8);
    out[2] = (unsigned char)(value >> 16);
    out[3] = (unsigned char)(value >> 24);
}

static uint32_t r6_glsl_float_bits(float value) {
    union {
        float f;
        uint32_t u;
    } bits;
    bits.f = value;
    return bits.u;
}

static int r6_glsl_region_bytes(const r6_glsl_region *region, size_t *bytes) {
    if (region->kind == R6_GLSL_SCALAR) {
        if (region->type != R6_GLSL_FLOAT && region->type != R6_GLSL_UINT) {
            return R6_ERR_ARG;
        }
        *bytes = 4;
        return R6_OK;
    }
    if (region->kind == R6_GLSL_VECTOR) {
        *bytes = 16;
        return R6_OK;
    }
    if (region->kind == R6_GLSL_MATRIX) {
        *bytes = 64;
        return R6_OK;
    }
    return R6_ERR_ARG;
}

int r6_glsl_pack_ubo(void *ubo, size_t capacity,
                     const r6_glsl_region *regions,
                     const r6_glsl_value *values, size_t count,
                     size_t *out_size) {
    unsigned char *bytes = (unsigned char *)ubo;
    size_t needed = 0;
    size_t index;

    if (!ubo || !regions || !values || !out_size) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < count; index++) {
        size_t bytes_per_member;
        size_t end;
        int rc = r6_glsl_region_bytes(&regions[index], &bytes_per_member);
        if (rc != R6_OK) {
            return rc;
        }
        if (regions[index].size != bytes_per_member) {
            return R6_ERR_ARG;
        }
        end = (size_t)regions[index].offset + bytes_per_member;
        if (end > capacity && end > needed) {
            needed = end;
        }
    }
    if (needed) {
        *out_size = needed;
        return R6_ERR_BUFFER;
    }

    r6_memset(ubo, 0, capacity);
    for (index = 0; index < count; index++) {
        unsigned char *target = bytes + regions[index].offset;
        const r6_glsl_value *value = &values[index];
        if (regions[index].kind == R6_GLSL_SCALAR) {
            uint32_t bits = regions[index].type == R6_GLSL_UINT
                ? value->u : r6_glsl_float_bits(value->f);
            r6_glsl_put_u32(target, bits);
        } else {
            size_t components = regions[index].kind == R6_GLSL_MATRIX
                ? 16 : 4;
            size_t part;
            for (part = 0; part < components; part++) {
                r6_glsl_put_u32(target + part * 4,
                                r6_glsl_float_bits(value->m[part]));
            }
        }
    }
    *out_size = capacity;
    return R6_OK;
}
