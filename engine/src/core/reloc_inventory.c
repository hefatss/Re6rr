/* Bounds-checked reader for the packed PE base relocation inventory. Only
 * copied facts cross the bridge; no image is mapped and no fixup is applied. */

#include "r6/r6_reloc_inventory.h"

#include "core/internal.h"

enum {
    R6_RELOC_HEADER_SIZE = 96,
    R6_RELOC_SECTION_SIZE = 8,
    R6_RELOC_BLOCK_SIZE = 20,
    R6_RELOC_ENTRY_SIZE = 8
};

static const unsigned char reloc_magic[8] = {
    'R', '6', 'R', 'L', 'C', 0, 1, 0
};

static size_t reloc_block_offset(const r6_reloc_header_t *header,
                                 uint32_t index) {
    return R6_RELOC_HEADER_SIZE +
           (size_t)header->section_count * R6_RELOC_SECTION_SIZE +
           (size_t)index * R6_RELOC_BLOCK_SIZE;
}

static size_t reloc_entry_offset(const r6_reloc_header_t *header,
                                 uint32_t index) {
    return reloc_block_offset(header, header->block_count) +
           (size_t)index * R6_RELOC_ENTRY_SIZE;
}

static int reloc_layout(const void *data, size_t size,
                        r6_reloc_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_reloc_header_t header;
    size_t sections;
    size_t blocks;
    size_t entries;
    size_t expected;
    size_t sum = 0;
    size_t types = 0;
    size_t previous = 0;
    uint32_t at;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_RELOC_HEADER_SIZE ||
            r6_memcmp(bytes, reloc_magic, sizeof(reloc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    r6_memset(&header, 0, sizeof(header));
    header.version = 1u;
    header.directory_rva = r6_u32(bytes, 12);
    header.directory_size = r6_u32(bytes, 16);
    header.section_count = r6_u32(bytes, 20);
    header.block_count = r6_u32(bytes, 24);
    header.entry_count = r6_u32(bytes, 28);
    for (at = 0; at < 16; at++) {
        header.type_counts[at] = r6_u32(bytes, 32 + (size_t)at * 4);
        types += header.type_counts[at];
    }
    if (!header.directory_rva || !header.directory_size ||
            !header.section_count || !header.block_count ||
            !header.entry_count || types != header.entry_count) {
        return R6_ERR_FORMAT;
    }
    sections = (size_t)header.section_count * R6_RELOC_SECTION_SIZE;
    blocks = (size_t)header.block_count * R6_RELOC_BLOCK_SIZE;
    if (sections / R6_RELOC_SECTION_SIZE != header.section_count ||
            blocks / R6_RELOC_BLOCK_SIZE != header.block_count ||
            header.entry_count > ((size_t)-1) / R6_RELOC_ENTRY_SIZE) {
        return R6_ERR_FORMAT;
    }
    entries = (size_t)header.entry_count * R6_RELOC_ENTRY_SIZE;
    expected = R6_RELOC_HEADER_SIZE + sections + blocks + entries;
    if (expected < R6_RELOC_HEADER_SIZE + sections ||
            expected < R6_RELOC_HEADER_SIZE + sections + blocks ||
            expected != size) {
        return R6_ERR_FORMAT;
    }
    if ((size_t)header.block_count * 8u > header.directory_size ||
            header.directory_size - (size_t)header.block_count * 8u !=
            (size_t)header.entry_count * 2u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.section_count; at++) {
        size_t row = R6_RELOC_HEADER_SIZE +
                     (size_t)at * R6_RELOC_SECTION_SIZE;
        uint32_t rva = r6_u32(bytes, row);
        uint32_t span = r6_u32(bytes, row + 4);
        if (!span || (at && rva < previous)) {
            return R6_ERR_FORMAT;
        }
        previous = (size_t)rva + span;
    }
    for (at = 0; at < header.block_count; at++) {
        size_t row = reloc_block_offset(&header, at);
        uint32_t block_size = r6_u32(bytes, row + 4);
        if (block_size < 8u || block_size % 2u) {
            return R6_ERR_FORMAT;
        }
        sum += block_size;
        if (sum > header.directory_size) {
            return R6_ERR_FORMAT;
        }
    }
    if (sum != header.directory_size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int reloc_read_section(const void *data, size_t size, uint32_t index,
                              const r6_reloc_header_t *header,
                              r6_reloc_section_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t row;
    if (index >= header->section_count || !out) {
        return R6_ERR_ARG;
    }
    (void)size;
    row = R6_RELOC_HEADER_SIZE + (size_t)index * R6_RELOC_SECTION_SIZE;
    out->rva = r6_u32(bytes, row);
    out->size = r6_u32(bytes, row + 4);
    return R6_OK;
}

static int reloc_read_block(const void *data, size_t size, uint32_t index,
                            const r6_reloc_header_t *header,
                            r6_reloc_block_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_reloc_section_t section;
    size_t row;
    uint32_t count;
    int result;
    if (index >= header->block_count || !out) {
        return R6_ERR_ARG;
    }
    (void)size;
    row = reloc_block_offset(header, index);
    out->page_rva = r6_u32(bytes, row);
    out->block_size = r6_u32(bytes, row + 4);
    out->entry_first = r6_u32(bytes, row + 8);
    out->entry_count = r6_u32(bytes, row + 12);
    out->section_index = r6_u32(bytes, row + 16);
    if (out->page_rva % R6_RELOC_PAGE_SIZE ||
            out->block_size < 8u || out->block_size % 2u ||
            out->section_index >= header->section_count) {
        return R6_ERR_FORMAT;
    }
    count = (out->block_size - 8u) / 2u;
    if (count != out->entry_count ||
            out->entry_first > header->entry_count ||
            out->entry_count > header->entry_count - out->entry_first) {
        return R6_ERR_FORMAT;
    }
    if (index + 1u < header->block_count) {
        uint32_t next = r6_u32(bytes, row + R6_RELOC_BLOCK_SIZE + 8);
        if (out->entry_first > next ||
                next - out->entry_first != out->entry_count) {
            return R6_ERR_FORMAT;
        }
    } else if (out->entry_first != header->entry_count - out->entry_count) {
        return R6_ERR_FORMAT;
    }
    result = reloc_read_section(data, size, out->section_index, header,
                                &section);
    if (result != R6_OK) {
        return result;
    }
    if (out->page_rva < section.rva ||
            (size_t)out->page_rva + R6_RELOC_PAGE_SIZE >
            (size_t)section.rva + section.size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_reloc_inventory_parse(const void *data, size_t size,
                             r6_reloc_header_t *out) {
    return reloc_layout(data, size, out);
}

int r6_reloc_inventory_section(const void *data, size_t size, uint32_t index,
                               r6_reloc_section_t *out) {
    r6_reloc_header_t header;
    int result = reloc_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return reloc_read_section(data, size, index, &header, out);
}

int r6_reloc_inventory_block(const void *data, size_t size, uint32_t index,
                             r6_reloc_block_t *out) {
    r6_reloc_header_t header;
    int result = reloc_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return reloc_read_block(data, size, index, &header, out);
}

int r6_reloc_inventory_entry(const void *data, size_t size, uint32_t index,
                             r6_reloc_entry_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_reloc_header_t header;
    r6_reloc_section_t section;
    r6_reloc_block_t block;
    size_t row;
    uint32_t at;
    uint32_t offset;
    uint32_t type;
    int result = reloc_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.entry_count || !out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.block_count; at++) {
        result = reloc_read_block(data, size, at, &header, &block);
        if (result != R6_OK) {
            return result;
        }
        if (index >= block.entry_first &&
                index - block.entry_first < block.entry_count) {
            break;
        }
    }
    if (at == header.block_count) {
        return R6_ERR_FORMAT;
    }
    result = reloc_read_section(data, size, block.section_index, &header,
                                &section);
    if (result != R6_OK) {
        return result;
    }
    row = reloc_entry_offset(&header, index);
    offset = r6_u32(bytes, row);
    type = r6_u32(bytes, row + 4);
    if (offset >= R6_RELOC_PAGE_SIZE || type >= 16u ||
            !header.type_counts[type]) {
        return R6_ERR_FORMAT;
    }
    if ((size_t)block.page_rva + offset < section.rva ||
            (size_t)block.page_rva + offset >=
            (size_t)section.rva + section.size) {
        return R6_ERR_FORMAT;
    }
    out->offset = offset;
    out->type = type;
    out->rva = block.page_rva + offset;
    out->block_index = at;
    return R6_OK;
}
