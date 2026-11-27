#include "core/internal.h"
#include "r6/r6_asset.h"

int r6_nut_container_facts(const void *data, size_t size,
                           r6_nut_container_facts_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_nut_container_facts_t facts;
    uint64_t payload_offset;
    uint64_t payload_end;
    uint32_t descriptor_size;
    uint32_t payload_size;
    uint16_t entries;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < 0x38 || (r6_memcmp(bytes, "NTWD", 4) != 0 &&
                        r6_memcmp(bytes, "NTLX", 4) != 0)) {
        return R6_ERR_FORMAT;
    }
    facts.container = (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) |
                      ((uint32_t)bytes[2] << 16) | ((uint32_t)bytes[3] << 24);
    facts.version = r6_u16(data, 0x04);
    entries = r6_u16(data, 0x06);
    facts.entries = entries;
    facts.total = ((uint64_t)r6_u32(data, 0x14) << 32) | r6_u32(data, 0x10);
    payload_size = r6_u32(data, 0x18);
    descriptor_size = r6_u32(data, 0x1C);
    facts.payload_size = payload_size;
    facts.descriptor_size = descriptor_size;
    facts.packed0 = r6_u32(data, 0x20);
    facts.packed1 = r6_u32(data, 0x24);
    facts.first_gidx = ((uint64_t)r6_u32(data, 0x34) << 32) |
                       r6_u32(data, 0x30);
    payload_offset = 0x10ull + (uint64_t)entries * descriptor_size;
    payload_end = payload_offset + (uint64_t)entries * payload_size;
    facts.payload_offset = payload_offset;
    facts.exact = (uint64_t)size == payload_end ? 1u : 0u;
    if ((facts.version != 1u && facts.version != 2u) || entries == 0u ||
            descriptor_size < 0x50u || payload_offset > size) {
        return R6_ERR_FORMAT;
    }
    *out = facts;
    return R6_OK;
}

int r6_ntwd_parse(const void *data, size_t size, r6_ntwd_header *out,
                  r6_ntwd_texture *textures, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ntwd_header header;
    size_t at;
    uint32_t i;
    if (!data || !out || size < 0x50 ||
        (r6_memcmp(data, "NTWD", 4) != 0 &&
         r6_memcmp(data, "NTLX", 4) != 0)) {
        return R6_ERR_FORMAT;
    }
    header.type = bytes[4];
    header.texture_count = r6_u16(data, 0x06);
    if ((header.type != 1 && header.type != 2) || header.texture_count == 0) {
        return R6_ERR_FORMAT;
    }
    *out = header;
    if (capacity < header.texture_count) {
        return R6_ERR_BUFFER;
    }
    at = 0x10;
    for (i = 0; i < header.texture_count; i++) {
        r6_ntwd_texture texture;
        size_t gidx;
        size_t extra;
        uint32_t block_size;
        uint32_t data_offset;
        if (at + 0x50 > size) {
            return R6_ERR_FORMAT;
        }
        block_size = r6_u32(data, at + 0x00);
        texture.data_size = r6_u32(data, at + 0x08);
        texture.header_stride = r6_u16(data, at + 0x0C);
        texture.faces = bytes[at + 0x11];
        texture.format = bytes[at + 0x13];
        texture.width = r6_u16(data, at + 0x14);
        texture.height = r6_u16(data, at + 0x16);
        texture.flags = r6_u32(data, at + 0x1C);
        data_offset = (header.type == 1)
                          ? (uint32_t)texture.header_stride
                          : r6_u32(data, at + 0x20);
        extra = texture.faces == 1
                    ? 0
                    : ((((size_t)texture.faces - 1) >> 2) + 1) * 0x10;
        gidx = at + 0x40 + extra + (((texture.flags >> 9) & 1) << 4);
        if (gidx + 0x10 > size || r6_memcmp(bytes + gidx, "GIDX", 4) != 0) {
            return R6_ERR_FORMAT;
        }
        texture.texture_id = r6_u32(data, gidx + 0x08);
        texture.header_offset = (uint32_t)at;
        texture.data_offset = data_offset;
        if ((size_t)at + data_offset > size ||
            texture.data_size > size - ((size_t)at + data_offset)) {
            return R6_ERR_FORMAT;
        }
        if (textures) {
            textures[i] = texture;
        }
        if (header.type == 1) {
            if (block_size < 0x50) {
                return R6_ERR_FORMAT;
            }
            at += block_size;
        } else {
            if (texture.header_stride < 0x50) {
                return R6_ERR_FORMAT;
            }
            at += texture.header_stride;
        }
    }
    return R6_OK;
}
