/* Bounds-checked config_3d.bin reader and dB-to-amplitude conversion. */

#include "core/internal.h"
#include "r6/r6_config_3d.h"

static const unsigned char config_version[3] = {1, 2, 3};

static float config_f32(const unsigned char *at) {
    union {
        uint32_t u;
        float f;
    } bits;
    bits.u = r6_u32(at, 0);
    return bits.f;
}

int r6_config_3d_init(r6_config_3d_view *view, const void *data, size_t size,
                      r6_config_3d_section *sections, uint32_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t count;
    uint32_t index;
    uint32_t record;
    if (!view || !bytes || size < R6_CONFIG_3D_HEADER_SIZE) {
        return R6_ERR_BUFFER;
    }
    if (r6_memcmp(bytes + 4, config_version, sizeof(config_version)) != 0) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 8);
    if (r6_u32(bytes, 12) != R6_CONFIG_3D_SECTION_STRIDE ||
        count > R6_CONFIG_3D_SECTION_MAX ||
        R6_CONFIG_3D_HEADER_SIZE + (size_t)count * R6_CONFIG_3D_SECTION_STRIDE >
            size) {
        return R6_ERR_FORMAT;
    }
    if (count && (!sections || capacity < count)) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(view->version, bytes + 4, sizeof(view->version));
    view->count = count;
    view->stride = R6_CONFIG_3D_SECTION_STRIDE;
    for (index = 0; index < 4; index++) {
        view->floats[index] = config_f32(bytes + 0x10 + index * 4);
    }
    for (index = 0; index < count; index++) {
        const unsigned char *base = bytes + R6_CONFIG_3D_HEADER_SIZE +
                                    (size_t)index * R6_CONFIG_3D_SECTION_STRIDE;
        r6_config_3d_section *out = sections + index;
        for (record = 0; record < R6_CONFIG_3D_RECORD_COUNT; record++) {
            const unsigned char *at = base +
                (size_t)record * R6_CONFIG_3D_RECORD_STRIDE;
            r6_config_3d_record *dst = out->records + record;
            dst->flags = r6_u32(at, 0);
            dst->db_start = config_f32(at + 4);
            dst->angle = config_f32(at + 8) + 90.0f;
            dst->db_end = config_f32(at + 12);
            dst->raw[0] = r6_u32(at, 16);
            dst->raw[1] = r6_u32(at, 20);
            dst->raw[2] = r6_u32(at, 24);
        }
        for (record = 0; record < R6_CONFIG_3D_TAIL_COUNT; record++) {
            out->tail[record] = r6_u32(base + R6_CONFIG_3D_TAIL_OFFSET,
                                       record * 4);
        }
    }
    view->sections = count ? sections : NULL;
    return R6_OK;
}

int r6_config_3d_amplitude(const r6_envelope_math *math, double db,
                           double zero_db, double *out) {
    if (!math || !math->pow_value || !out) {
        return R6_ERR_ARG;
    }
    if (db <= zero_db) {
        *out = 0.0;
        return R6_OK;
    }
    *out = math->pow_value(math->user, 10.0,
                           db * R6_CONFIG_3D_DB_TO_AMPLITUDE_SCALE);
    return R6_OK;
}
