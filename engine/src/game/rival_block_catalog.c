/* Bounds-checked reader for packed story-rival block inventories. */

#include "r6/r6_rival_block_catalog.h"

#include "core/internal.h"

enum {
    R6_RVB_HEADER_SIZE = 36,
    R6_RVB_BLOCK_SIZE = 76,
    R6_RVB_FILES = 1,
    R6_RVB_BLOCKS = 398,
    R6_RVB_UNIQUE = 201,
    R6_RVB_SOURCE = 145966,
    R6_RVB_LINES = 5261,
    R6_RVB_KEYWORDS = 5,
    R6_RVB_MAX_STRING = 96
};

static const unsigned char rvb_magic[8] = {
    'R', '6', 'R', 'V', 'B', 0, 1, 0
};

static const char *const rvb_keywords[5] = {
    "Band", "Feature", "StartConfig", "EventFirst", "EventLast"
};

static int rvb_header(const void *data, size_t size,
                      r6_rival_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_rival_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_RVB_HEADER_SIZE ||
            r6_memcmp(bytes, rvb_magic, sizeof(rvb_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_RVB_FILES ||
            r6_u32(bytes, 16) != R6_RVB_BLOCKS ||
            r6_u32(bytes, 20) != R6_RVB_UNIQUE || !r6_u32(bytes, 24) ||
            r6_u32(bytes, 28) != R6_RVB_SOURCE ||
            r6_u32(bytes, 32) != R6_RVB_LINES) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.block_count = r6_u32(bytes, 16);
    header.unique_count = r6_u32(bytes, 20);
    header.string_size = r6_u32(bytes, 24);
    header.source_bytes = r6_u32(bytes, 28);
    header.lines = r6_u32(bytes, 32);
    base = R6_RVB_HEADER_SIZE +
           (header.block_count + header.file_count) * R6_RVB_BLOCK_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t rvb_strings_base(void) {
    return R6_RVB_HEADER_SIZE +
           (R6_RVB_BLOCKS + R6_RVB_FILES) * R6_RVB_BLOCK_SIZE;
}

static int rvb_string(const void *data,
                      const r6_rival_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = rvb_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_RVB_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value < 0x20u || value > 0x7eu) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int rvb_copy(const void *data,
                    const r6_rival_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = rvb_string(data, header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int rvb_path(const void *data, size_t size, char *out,
                    size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_rival_header_t header;
    uint32_t offset;
    uint32_t length;
    int result = rvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    offset = r6_u32(bytes, R6_RVB_HEADER_SIZE);
    length = r6_u32(bytes, R6_RVB_HEADER_SIZE + 4);
    if (rvb_string(data, &header, offset, length) != R6_OK ||
            r6_memcmp(bytes + offset + length - 4, ".txt", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    return rvb_copy(data, &header, offset, length, out, capacity);
}

static int rvb_block(const void *data,
                     const r6_rival_header_t *header,
                     uint32_t index, r6_rival_block_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_rival_block_t block;
    size_t at = R6_RVB_HEADER_SIZE +
                (size_t)(index + 1) * R6_RVB_BLOCK_SIZE;
    uint32_t keyword;
    if (index >= header->block_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&block, bytes + at, sizeof(block));
    if (block.name_length < 16 ||
            r6_memcmp(bytes + block.name_offset, "ECharacter_", 11) != 0 ||
            rvb_string(data, header, block.name_offset,
                       block.name_length) != R6_OK ||
            !block.line_count || block.line_start > header->lines ||
            block.line_count > header->lines - block.line_start) {
        return R6_ERR_FORMAT;
    }
    for (keyword = 0; keyword < R6_RVB_KEYWORDS; keyword++) {
        size_t expected = r6_strlen(rvb_keywords[keyword]);
        const unsigned char *text = bytes + block.row_offset[keyword];
        if (!block.count[keyword] ||
            rvb_string(data, header, block.row_offset[keyword],
                       block.row_length[keyword]) != R6_OK ||
            block.row_length[keyword] < expected ||
            r6_memcmp(text, rvb_keywords[keyword], expected) != 0 ||
            (block.row_length[keyword] != expected &&
             text[expected] != ' ')) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &block, sizeof(block));
    return R6_OK;
}

int r6_rival_parse(const void *data, size_t size, r6_rival_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_rival_header_t header;
    r6_rival_block_t block;
    char path[R6_RVB_MAX_STRING + 1];
    uint32_t last_end = 0;
    uint32_t unique = 0;
    uint32_t at;
    uint32_t other;
    int result = rvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if (rvb_path(data, size, path, sizeof(path)) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.block_count; at++) {
        result = rvb_block(data, &header, at, &block);
        if (result != R6_OK || block.line_start < last_end) {
            return R6_ERR_FORMAT;
        }
        last_end = block.line_start + block.line_count;
        unique++;
        for (other = 0; other < at; other++) {
            size_t prior_at = R6_RVB_HEADER_SIZE +
                              (size_t)(other + 1) * R6_RVB_BLOCK_SIZE;
            uint32_t prior_length = r6_u32(bytes, prior_at + 4);
            if (prior_length == block.name_length &&
                    r6_memcmp(bytes + r6_u32(bytes, prior_at),
                              bytes + block.name_offset,
                              block.name_length) == 0) {
                unique--;
                break;
            }
        }
    }
    if (last_end > header.lines || unique != header.unique_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_rival_path(const void *data, size_t size, char *out,
                  size_t capacity) {
    r6_rival_header_t header;
    int result = rvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return rvb_path(data, size, out, capacity);
}

int r6_rival_block(const void *data, size_t size, uint32_t index,
                   r6_rival_block_t *out) {
    r6_rival_header_t header;
    int result = rvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return rvb_block(data, &header, index, out);
}

int r6_rival_name(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    r6_rival_header_t header;
    r6_rival_block_t block;
    int result = rvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = rvb_block(data, &header, index, &block);
    if (result != R6_OK) {
        return result;
    }
    return rvb_copy(data, &header, block.name_offset, block.name_length,
                    out, capacity);
}

int r6_rival_keyword(const void *data, size_t size, uint32_t index,
                     uint32_t keyword, char *out, size_t capacity) {
    r6_rival_header_t header;
    r6_rival_block_t block;
    int result = rvb_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = rvb_block(data, &header, index, &block);
    if (result != R6_OK) {
        return result;
    }
    if (keyword >= R6_RVB_KEYWORDS) {
        return R6_ERR_ARG;
    }
    return rvb_copy(data, &header, block.row_offset[keyword],
                    block.row_length[keyword], out, capacity);
}

