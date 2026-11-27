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

static int ndwd_sec0_end(const r6_ndwd_header *header, size_t *out) {
    uint64_t end = 0x50ull + header->section_size[0];
    if (end > 0xFFFFFFFFull) {
        return 0;
    }
    *out = (size_t)end;
    return 1;
}

static int ndwd_string_base(const r6_ndwd_header *header, size_t size,
                            size_t *out) {
    uint64_t base = 0x30ull;
    uint32_t index;
    for (index = 0; index < 4u; index++) {
        base += header->section_size[index];
    }
    if (base >= size || base > 0xFFFFFFFFull) {
        return 0;
    }
    *out = (size_t)base;
    return 1;
}

int r6_ndwd_parse_subrecord(const void *data, size_t size,
                            const r6_ndwd_header *header,
                            const r6_ndwd_group *group, uint32_t index,
                            r6_ndwd_subrecord_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ndwd_subrecord_t row;
    size_t end;
    uint64_t at;
    uint64_t chain;
    uint32_t part;
    if (!bytes || !header || !group || !out || index >= group->subrecord_count ||
        !ndwd_bounds(data, size, header) || !ndwd_sec0_end(header, &end)) {
        return R6_ERR_ARG;
    }
    at = (uint64_t)group->subrecord_start + (uint64_t)index * 0x30u;
    if (at + 0x30u > end) {
        return R6_ERR_FORMAT;
    }
    row.offset = (uint32_t)at;
    for (part = 0; part < 4u; part++) {
        row.tokens[part] = r6_u32(bytes, (size_t)at + 0x10u + part * 4u);
    }
    row.extra = r6_u16(bytes, (size_t)at + 0x0Au);
    chain = at + 0x20u + (uint64_t)row.extra * 0x18u;
    if (chain + 0x10u > end) {
        return R6_ERR_FORMAT;
    }
    row.chain_offset = (uint32_t)chain;
    *out = row;
    return R6_OK;
}

int r6_ndwd_parse_chain_record(const void *data, size_t size,
                               const r6_ndwd_header *header,
                               const r6_ndwd_subrecord_t *sub,
                               uint32_t index, r6_ndwd_chain_record_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ndwd_chain_record_t row;
    size_t end;
    uint64_t at;
    uint32_t part;
    if (!bytes || !header || !sub || !out || !ndwd_bounds(data, size, header) ||
        !ndwd_sec0_end(header, &end)) {
        return R6_ERR_ARG;
    }
    at = sub->chain_offset;
    for (part = 0; part <= index; part++) {
        if (at + 0x10u > end) {
            return R6_ERR_FORMAT;
        }
        row.offset = (uint32_t)at;
        row.stride = r6_u32(bytes, (size_t)at);
        row.name_offset = r6_u32(bytes, (size_t)at + 4u);
        row.flag = bytes[(size_t)at + 0x0Bu];
        if (part == index) {
            *out = row;
            return R6_OK;
        }
        if (!row.stride || !row.flag) {
            return R6_ERR_NOT_FOUND;
        }
        at += row.stride;
        if (at > 0xFFFFFFFFull) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_ndwd_string(const void *data, size_t size,
                   const r6_ndwd_header *header, uint32_t offset,
                   char *out, size_t capacity, size_t *used) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base;
    uint64_t at;
    size_t length = 0;
    if (!bytes || !header || !out || !capacity ||
        !ndwd_bounds(data, size, header) ||
        !ndwd_string_base(header, size, &base)) {
        return R6_ERR_ARG;
    }
    at = (uint64_t)base + offset;
    if (at >= size) {
        return R6_ERR_FORMAT;
    }
    while (at + length < size && bytes[(size_t)at + length]) {
        length++;
    }
    if (at + length >= size) {
        return R6_ERR_FORMAT;
    }
    length++;
    if (used) {
        *used = length;
    }
    if (capacity < length) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + (size_t)at, length);
    return R6_OK;
}
