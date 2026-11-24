#include "core/internal.h"
#include "r6/r6_asset.h"

static int ndwd_bounds(const void *data, size_t size, const r6_ndwd_header *h) {
    size_t section0 = (size_t)h->section_size[0];
    if (0x50 + section0 < 0x50 || 0x50 + section0 > size) {
        return 0;
    }
    return 1;
}

int r6_ndwd_parse_header(const void *data, size_t size, r6_ndwd_header *out) {
    r6_ndwd_header header;
    if (!data || !out || size < 0x50 ||
        r6_memcmp(data, "NDWD", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    header.id = r6_u32(data, 0x04);
    header.version = r6_u16(data, 0x08);
    header.group_count = r6_u16(data, 0x0A);
    header.section_size[0] = r6_u32(data, 0x10);
    header.section_size[1] = r6_u32(data, 0x14);
    header.section_size[2] = r6_u32(data, 0x18);
    header.section_size[3] = r6_u32(data, 0x1C);
    if (header.version != 2 || !ndwd_bounds(data, size, &header)) {
        return R6_ERR_FORMAT;
    }
    if (0x30 + (size_t)header.group_count * 0x30 >
        0x50 + (size_t)header.section_size[0]) {
        return R6_ERR_FORMAT;
    }
    *out = header;
    return R6_OK;
}

int r6_ndwd_parse_group(const void *data, size_t size,
                        const r6_ndwd_header *header, uint32_t index,
                        r6_ndwd_group *out) {
    r6_ndwd_group group;
    size_t at;
    if (!data || !header || !out || index >= header->group_count ||
        !ndwd_bounds(data, size, header)) {
        return R6_ERR_ARG;
    }
    at = 0x30 + (size_t)index * 0x30;
    group.offset = (uint32_t)at;
    group.name_offset = r6_u32(data, at + 0x20);
    group.subrecord_count = r6_u16(data, at + 0x2A);
    group.subrecord_start = r6_u32(data, at + 0x2C);
    if ((size_t)group.subrecord_start +
            (size_t)group.subrecord_count * 0x30 >
        0x50 + (size_t)header->section_size[0]) {
        return R6_ERR_FORMAT;
    }
    *out = group;
    return R6_OK;
}
