#include "core/internal.h"
#include "r6/r6_asset.h"

/* CPU reconstruction of the five shipped .nut pixel formats. No files,
 * allocation, CRT or libm: caller owns all bytes. */

static int r6_nut_cube(const r6_ntwd_texture *texture) {
    return ((texture->flags >> 9) & 1u) != 0 ||
           ((texture->flags >> 0x11) & 1u) != 0;
}

static uint64_t r6_nut_level_bytes(uint8_t format, uint32_t width,
                                   uint32_t height) {
    uint64_t size;
    if (format == 0x0e || format == 0x15) {
        size = (uint64_t)width * height * 4;
    } else if (format <= 2) {
        uint64_t blocks = ((uint64_t)(width + 3) / 4) *
                          ((uint64_t)(height + 3) / 4);
        size = blocks * (format == 0 ? 8u : 16u);
    } else {
        return 0;
    }
    return (size + 15) & ~(uint64_t)15;
}

static uint64_t r6_nut_chain_bytes(const r6_ntwd_texture *texture,
                                   uint32_t levels, uint32_t width,
                                   uint32_t height) {
    uint64_t total = 0;
    uint32_t level;
    for (level = 0; level < levels; level++) {
        uint32_t w = width >> level;
        uint32_t h = height >> level;
        total += r6_nut_level_bytes(texture->format, w ? w : 1, h ? h : 1);
    }
    return total;
}

/* Three NPOT BC3 textures store one level fewer than byte +0x11 declares. */
static uint32_t r6_nut_level_count(const r6_ntwd_texture *texture,
                                   uint64_t face_size) {
    uint32_t declared = texture->faces;
    uint32_t level;
    uint64_t total = 0;
    if (declared == 0) {
        return 0;
    }
    for (level = 0; level < declared; level++) {
        uint32_t w = texture->width >> level;
        uint32_t h = texture->height >> level;
        uint64_t size = r6_nut_level_bytes(texture->format, w ? w : 1,
                                           h ? h : 1);
        if (size == 0 || total + size > face_size) {
            return level;
        }
        total += size;
    }
    return declared;
}

int r6_nut_layout_facts(const r6_ntwd_texture *texture,
                        r6_nut_layout_facts_t *out) {
    uint32_t faces;
    uint32_t declared;
    uint64_t face_expected;
    uint64_t level0;
    if (!texture || !out) {
        return R6_ERR_ARG;
    }
    if (texture->format != 0 && texture->format != 1 &&
        texture->format != 2 && texture->format != 0x0e &&
        texture->format != 0x15) {
        return R6_ERR_FORMAT;
    }
    declared = texture->faces;
    if (!declared || !texture->width || !texture->height) {
        return R6_ERR_FORMAT;
    }
    level0 = r6_nut_level_bytes(texture->format, texture->width,
                                texture->height);
    face_expected = r6_nut_chain_bytes(texture, declared, texture->width,
                                       texture->height);
    if (!level0 || !face_expected) {
        return R6_ERR_FORMAT;
    }
    faces = r6_nut_cube(texture) ? 6u : 1u;
    if (face_expected > ~(uint64_t)0 / faces) {
        return R6_ERR_FORMAT;
    }
    r6_memset(out, 0, sizeof(*out));
    out->expected_size = face_expected * faces;
    out->face_size = face_expected;
    out->level0_bytes = level0;
    out->declared_levels = declared;
    out->available_levels = r6_nut_level_count(
        texture, (uint64_t)texture->data_size / faces);
    out->cube = faces == 6u ? 1u : 0u;
    return R6_OK;
}

static void r6_nut_rgb565(uint16_t value, unsigned char out[3]) {
    out[0] = (unsigned char)(((value >> 11) & 0x1fu) * 255u / 31u);
    out[1] = (unsigned char)(((value >> 5) & 0x3fu) * 255u / 63u);
    out[2] = (unsigned char)((value & 0x1fu) * 255u / 31u);
}

static uint8_t r6_nut_bc3_alpha(uint8_t a0, uint8_t a1, uint8_t index) {
    if (a0 > a1) {
        return (uint8_t)(((7u - index) * a0 + index * a1 + 3u) / 7u);
    }
    if (index < 2) {
        return index == 0 ? a0 : a1;
    }
    if (index == 6) {
        return 0;
    }
    if (index == 7) {
        return 255;
    }
    return (uint8_t)(((6u - index) * a0 + (index - 1u) * a1 + 2u) / 5u);
}

static void r6_nut_bc_block(uint8_t format, const unsigned char *block,
                            unsigned char pixels[16][4]) {
    unsigned char alpha[16];
    uint16_t c0, c1;
    unsigned char a[3], b[3], c[3], d[3];
    uint32_t indices;
    uint32_t i;
    if (format == 1) {
        for (i = 0; i < 8; i++) {
            alpha[i * 2] = (unsigned char)((block[i] & 0xfu) * 17u);
            alpha[i * 2 + 1] = (unsigned char)((block[i] >> 4) * 17u);
        }
        block += 8;
    } else if (format == 2) {
        uint64_t bits = 0;
        uint8_t a0 = block[0];
        uint8_t a1 = block[1];
        for (i = 0; i < 6; i++) {
            bits |= (uint64_t)block[2 + i] << (8 * i);
        }
        for (i = 0; i < 16; i++) {
            alpha[i] = r6_nut_bc3_alpha(a0, a1,
                                        (uint8_t)((bits >> (3 * i)) & 7u));
        }
        block += 8;
    } else {
        for (i = 0; i < 16; i++) {
            alpha[i] = 255;
        }
    }

    c0 = (uint16_t)(block[0] | ((uint16_t)block[1] << 8));
    c1 = (uint16_t)(block[2] | ((uint16_t)block[3] << 8));
    indices = (uint32_t)block[4] | ((uint32_t)block[5] << 8) |
              ((uint32_t)block[6] << 16) | ((uint32_t)block[7] << 24);
    r6_nut_rgb565(c0, a);
    r6_nut_rgb565(c1, b);
    if (c0 > c1) {
        for (i = 0; i < 3; i++) {
            c[i] = (unsigned char)((2u * a[i] + b[i]) / 3u);
            d[i] = (unsigned char)((a[i] + 2u * b[i]) / 3u);
        }
    } else {
        for (i = 0; i < 3; i++) {
            c[i] = (unsigned char)((a[i] + b[i]) / 2u);
            d[i] = 0;
        }
    }
    for (i = 0; i < 16; i++) {
        unsigned char *pixel = pixels[i];
        const unsigned char *color;
        uint32_t index = (indices >> (2 * i)) & 3u;
        if (index == 0) {
            color = a;
        } else if (index == 1) {
            color = b;
        } else if (index == 2) {
            color = c;
        } else {
            color = d;
        }
        pixel[0] = color[0];
        pixel[1] = color[1];
        pixel[2] = color[2];
        pixel[3] = alpha[i];
    }
}

int r6_nut_decode_rgba(const void *data, size_t size,
                       const r6_ntwd_texture *texture, uint32_t level,
                       uint32_t face, void *out, size_t capacity,
                       size_t *out_size) {
    const unsigned char *bytes = (const unsigned char *)data;
    unsigned char *dst = (unsigned char *)out;
    uint64_t face_size;
    uint64_t level_offset = 0;
    uint64_t level_bytes;
    uint64_t start;
    uint32_t levels;
    uint32_t width, height, required, block_bytes;
    uint32_t l;
    int cube;

    if (!data || !texture || !out_size) {
        return R6_ERR_ARG;
    }
    if (texture->format != 0 && texture->format != 1 &&
        texture->format != 2 && texture->format != 0x0e &&
        texture->format != 0x15) {
        return R6_ERR_FORMAT;
    }
    cube = r6_nut_cube(texture);
    if (face >= (cube ? 6u : 1u)) {
        return R6_ERR_ARG;
    }
    face_size = (uint64_t)texture->data_size / (cube ? 6u : 1u);
    levels = r6_nut_level_count(texture, face_size);
    if (level >= levels) {
        return R6_ERR_ARG;
    }
    width = texture->width >> level;
    height = texture->height >> level;
    width = width ? width : 1;
    height = height ? height : 1;
    required = width * height * 4u;
    *out_size = required;
    if (capacity < required || !out) {
        return R6_ERR_BUFFER;
    }

    for (l = 0; l < level; l++) {
        uint32_t w = texture->width >> l;
        uint32_t h = texture->height >> l;
        level_offset += r6_nut_level_bytes(texture->format, w ? w : 1,
                                           h ? h : 1);
    }
    level_bytes = r6_nut_level_bytes(texture->format, width, height);
    if (level_bytes == 0 || level_offset + level_bytes > face_size) {
        return R6_ERR_FORMAT;
    }
    start = (uint64_t)texture->header_offset + texture->data_offset +
            (uint64_t)face * face_size + level_offset;
    if (start > size || (uint64_t)size - start < (uint64_t)level_bytes) {
        return R6_ERR_FORMAT;
    }
    bytes += (size_t)start;

    if (texture->format == 0x0e || texture->format == 0x15) {
        uint32_t i;
        for (i = 0; i < width * height; i++) {
            if (texture->format == 0x0e) {
                /* ARGB8 byte order: alpha, red, green, blue. */
                dst[i * 4] = bytes[i * 4 + 1];
                dst[i * 4 + 1] = bytes[i * 4 + 2];
                dst[i * 4 + 2] = bytes[i * 4 + 3];
                dst[i * 4 + 3] = bytes[i * 4];
            } else {
                dst[i * 4] = bytes[i * 4 + 2];
                dst[i * 4 + 1] = bytes[i * 4 + 1];
                dst[i * 4 + 2] = bytes[i * 4];
                dst[i * 4 + 3] = bytes[i * 4 + 3];
            }
        }
        return R6_OK;
    }

    block_bytes = texture->format == 0 ? 8u : 16u;
    {
        uint32_t blocks_x = (width + 3) / 4;
        uint32_t blocks_y = (height + 3) / 4;
        uint32_t by, bx;
        for (by = 0; by < blocks_y; by++) {
            for (bx = 0; bx < blocks_x; bx++) {
                unsigned char pixels[16][4];
                uint64_t at = ((uint64_t)by * blocks_x + bx) * block_bytes;
                uint32_t x, y;
                if (at + block_bytes > level_bytes) {
                    return R6_ERR_FORMAT;
                }
                r6_nut_bc_block(texture->format, bytes + (size_t)at, pixels);
                for (y = 0; y < 4; y++) {
                    uint32_t py = by * 4 + y;
                    if (py >= height) {
                        continue;
                    }
                    for (x = 0; x < 4; x++) {
                        uint32_t px = bx * 4 + x;
                        size_t dst_at;
                        if (px >= width) {
                            continue;
                        }
                        dst_at = ((size_t)py * width + px) * 4;
                        dst[dst_at] = pixels[y * 4 + x][0];
                        dst[dst_at + 1] = pixels[y * 4 + x][1];
                        dst[dst_at + 2] = pixels[y * 4 + x][2];
                        dst[dst_at + 3] = pixels[y * 4 + x][3];
                    }
                }
            }
        }
    }
    return R6_OK;
}
