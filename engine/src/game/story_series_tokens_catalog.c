/* Bounds-checked reader for packed story-series token lines. */

#include "r6/r6_story_series_tokens_catalog.h"

#include "core/internal.h"

enum {
    R6_SST_HEADER_SIZE = 32,
    R6_SST_BLOCK_SIZE = 12,
    R6_SST_SPAN_SIZE = 8,
    R6_SST_BLOCKS = 125,
    R6_SST_LINES = 1249,
    R6_SST_SOURCE_SIZE = 28433,
    R6_SST_SOURCE_LINES = 1511,
    R6_SST_MAX_STRING = 96
};

static const unsigned char sst_magic[8] = {
    'R', '6', 'S', 'S', 'T', 0, 1, 0
};

static int sst_header(const void *data, size_t size,
                      r6_story_series_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_story_series_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SST_HEADER_SIZE ||
            r6_memcmp(bytes, sst_magic, sizeof(sst_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_SST_BLOCKS ||
            r6_u32(bytes, 16) != R6_SST_LINES || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_SST_SOURCE_SIZE ||
            r6_u32(bytes, 28) != R6_SST_SOURCE_LINES) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.block_count = r6_u32(bytes, 12);
    header.line_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_size = r6_u32(bytes, 24);
    header.source_lines = r6_u32(bytes, 28);
    base = R6_SST_HEADER_SIZE +
           (size_t)header.block_count * R6_SST_BLOCK_SIZE +
           (size_t)header.line_count * R6_SST_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t sst_lines_base(void) {
    return R6_SST_HEADER_SIZE + R6_SST_BLOCKS * R6_SST_BLOCK_SIZE;
}

static size_t sst_strings_base(void) {
    return sst_lines_base() + R6_SST_LINES * R6_SST_SPAN_SIZE;
}

static int sst_string(const void *data,
                      const r6_story_series_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = sst_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > R6_SST_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        unsigned char value = bytes[(size_t)offset + at];
        if (value != 0x09u && (value < 0x20u || value > 0x7eu)) {
            return R6_ERR_FORMAT;
        }
    }
    return R6_OK;
}

static int sst_copy(const void *data,
                    const r6_story_series_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = sst_string(data, header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int sst_block(const void *data, size_t size, uint32_t index,
                     r6_story_series_block_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_story_series_header_t header;
    r6_story_series_block_t block;
    size_t at;
    int result = sst_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.block_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_SST_HEADER_SIZE + (size_t)index * R6_SST_BLOCK_SIZE;
    r6_memcpy(&block, bytes + at, sizeof(block));
    if (!block.lines || block.lines > header.line_count ||
            block.header_length < 8 ||
            sst_string(data, &header, block.header_offset,
                       block.header_length) != R6_OK ||
            r6_memcmp(bytes + block.header_offset, "ESeries_", 8) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &block, sizeof(block));
    return R6_OK;
}

static int sst_line(const void *data,
                    const r6_story_series_header_t *header,
                    uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at;
    if (index >= header->line_count) {
        return R6_ERR_ARG;
    }
    at = sst_lines_base() + (size_t)index * R6_SST_SPAN_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    return sst_copy(data, header, offset, length, out, capacity);
}

int r6_story_series_parse(const void *data, size_t size,
                          r6_story_series_header_t *out) {
    r6_story_series_header_t header;
    r6_story_series_block_t block;
    char text[R6_SST_MAX_STRING + 1];
    uint32_t lines = 0;
    uint32_t at;
    int result = sst_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.block_count; at++) {
        result = sst_block(data, size, at, &block);
        if (result != R6_OK || block.lines > header.line_count - lines) {
            return R6_ERR_FORMAT;
        }
        lines += block.lines;
    }
    if (lines != header.line_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.line_count; at++) {
        result = sst_line(data, &header, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_story_series_block(const void *data, size_t size, uint32_t index,
                          r6_story_series_block_t *out) {
    return sst_block(data, size, index, out);
}

int r6_story_series_header(const void *data, size_t size, uint32_t index,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_story_series_header_t header;
    r6_story_series_block_t block;
    int result = sst_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = sst_block(data, size, index, &block);
    if (result != R6_OK) {
        return result;
    }
    return sst_copy(data, &header, block.header_offset,
                    block.header_length, out, capacity);
}

int r6_story_series_line(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    r6_story_series_header_t header;
    int result = sst_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return sst_line(data, &header, index, out, capacity);
}
