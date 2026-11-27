/* Bounds-checked reader for packed LOADLIST facts. Only copied strings,
 * offsets and sizes cross the bridge; section geometry is not read. */

#include "r6/r6_loadlist_catalog.h"

#include "core/internal.h"

enum {
    R6_LOADLIST_HEADER_SIZE = 32,
    R6_LOADLIST_FILE_SIZE = 16,
    R6_LOADLIST_BLOCK_SIZE = 32,
    R6_LOADLIST_STREAM_SIZE = 16
};

static const unsigned char loadlist_magic[8] = {
    'R', '6', 'L', 'L', 'S', 0, 1, 0
};

static int loadlist_layout(const void *data, size_t size,
                           r6_loadlist_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_loadlist_header_t header;
    size_t files;
    size_t blocks;
    size_t streams;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_LOADLIST_HEADER_SIZE ||
            r6_memcmp(bytes, loadlist_magic, sizeof(loadlist_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.block_count = r6_u32(bytes, 16);
    header.stream_count = r6_u32(bytes, 20);
    header.strings_size = r6_u32(bytes, 24);
    header.reserved = r6_u32(bytes, 28);
    if (!header.file_count || !header.block_count || !header.stream_count ||
            !header.strings_size || header.reserved ||
            header.file_count > ((size_t)-1 - R6_LOADLIST_HEADER_SIZE) /
                                R6_LOADLIST_FILE_SIZE ||
            header.block_count > ((size_t)-1 - R6_LOADLIST_HEADER_SIZE -
                                  (size_t)header.file_count *
                                  R6_LOADLIST_FILE_SIZE) /
                                 R6_LOADLIST_BLOCK_SIZE ||
            header.stream_count > ((size_t)-1 - R6_LOADLIST_HEADER_SIZE -
                                   (size_t)header.file_count *
                                   R6_LOADLIST_FILE_SIZE -
                                   (size_t)header.block_count *
                                   R6_LOADLIST_BLOCK_SIZE) /
                                  R6_LOADLIST_STREAM_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_LOADLIST_FILE_SIZE;
    blocks = (size_t)header.block_count * R6_LOADLIST_BLOCK_SIZE;
    streams = (size_t)header.stream_count * R6_LOADLIST_STREAM_SIZE;
    if ((size_t)R6_LOADLIST_HEADER_SIZE + files + blocks + streams > size ||
            header.strings_size != size - R6_LOADLIST_HEADER_SIZE - files -
            blocks - streams) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int loadlist_string(const void *data, size_t size, uint32_t offset,
                           char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_loadlist_header_t header;
    size_t strings_off;
    size_t end;
    uint32_t at;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_LOADLIST_HEADER_SIZE +
                  (size_t)header.file_count * R6_LOADLIST_FILE_SIZE +
                  (size_t)header.block_count * R6_LOADLIST_BLOCK_SIZE +
                  (size_t)header.stream_count * R6_LOADLIST_STREAM_SIZE;
    end = strings_off + header.strings_size;
    if (offset < strings_off || offset >= end) {
        return R6_ERR_FORMAT;
    }
    at = offset;
    while (at < end && bytes[at]) {
        at++;
    }
    if (at == end || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

static uint32_t loadlist_row_at(const void *data, size_t count, size_t stride,
                                uint32_t index) {
    return (uint32_t)(R6_LOADLIST_HEADER_SIZE + count * stride +
                      (size_t)index * stride);
}

int r6_loadlist_parse(const void *data, size_t size,
                      r6_loadlist_header_t *out) {
    return loadlist_layout(data, size, out);
}

int r6_loadlist_file(const void *data, size_t size, uint32_t index,
                     r6_loadlist_file_t *out) {
    const unsigned char *bytes;
    r6_loadlist_header_t header;
    uint32_t row;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = loadlist_row_at(data, 0, R6_LOADLIST_FILE_SIZE, index);
    out->block_first = r6_u32(bytes, row + 8);
    out->block_count = r6_u32(bytes, row + 12);
    if (out->block_first > header.block_count ||
            out->block_count > header.block_count - out->block_first) {
        return R6_ERR_FORMAT;
    }
    if (index + 1u < header.file_count) {
        uint32_t next = r6_u32(bytes, row + R6_LOADLIST_FILE_SIZE + 8);
        if (out->block_first > next ||
                next - out->block_first != out->block_count) {
            return R6_ERR_FORMAT;
        }
    } else if (out->block_first != header.block_count - out->block_count) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_loadlist_path(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_loadlist_header_t header;
    uint32_t row;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = loadlist_row_at(data, 0, R6_LOADLIST_FILE_SIZE, index);
    return loadlist_string(data, size, r6_u32(bytes, row), out, capacity);
}

int r6_loadlist_block(const void *data, size_t size, uint32_t index,
                      r6_loadlist_block_t *out) {
    const unsigned char *bytes;
    r6_loadlist_header_t header;
    uint32_t row;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.block_count || !out) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_LOADLIST_HEADER_SIZE +
                     (size_t)header.file_count * R6_LOADLIST_FILE_SIZE +
                     (size_t)index * R6_LOADLIST_BLOCK_SIZE);
    out->section = r6_u32(bytes, row);
    out->source_size = r6_u32(bytes, row + 12);
    out->inflated_size = r6_u32(bytes, row + 16);
    out->wrapped = r6_u32(bytes, row + 20);
    out->stream_first = r6_u32(bytes, row + 24);
    out->stream_count = r6_u32(bytes, row + 28);
    if (!out->source_size || out->inflated_size < R6_LOADLIST_MIN_STREAM ||
            out->wrapped > 1u ||
            out->stream_first > header.stream_count ||
            out->stream_count > header.stream_count - out->stream_first) {
        return R6_ERR_FORMAT;
    }
    if (index + 1u < header.block_count) {
        uint32_t next = r6_u32(bytes, row + R6_LOADLIST_BLOCK_SIZE + 24);
        if (out->stream_first > next ||
                next - out->stream_first != out->stream_count) {
            return R6_ERR_FORMAT;
        }
    } else if (out->stream_first !=
               header.stream_count - out->stream_count) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_loadlist_bin_path(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_loadlist_header_t header;
    uint32_t row;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.block_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_LOADLIST_HEADER_SIZE +
                     (size_t)header.file_count * R6_LOADLIST_FILE_SIZE +
                     (size_t)index * R6_LOADLIST_BLOCK_SIZE);
    return loadlist_string(data, size, r6_u32(bytes, row + 4), out, capacity);
}

static int loadlist_owner(const void *data, size_t size, uint32_t index,
                          uint32_t *owner) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_loadlist_header_t header;
    size_t row;
    uint32_t at;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.block_count; at++) {
        row = R6_LOADLIST_HEADER_SIZE +
              (size_t)header.file_count * R6_LOADLIST_FILE_SIZE +
              (size_t)at * R6_LOADLIST_BLOCK_SIZE;
        if (index >= r6_u32(bytes, row + 24) &&
                index - r6_u32(bytes, row + 24) < r6_u32(bytes, row + 28)) {
            *owner = at;
            return R6_OK;
        }
    }
    return R6_ERR_FORMAT;
}

static uint32_t loadlist_stream_row(const void *data, size_t size,
                                    uint32_t index) {
    r6_loadlist_header_t header;
    if (loadlist_layout(data, size, &header) != R6_OK) {
        return 0;
    }
    return (uint32_t)(R6_LOADLIST_HEADER_SIZE +
                      (size_t)header.file_count * R6_LOADLIST_FILE_SIZE +
                      (size_t)header.block_count * R6_LOADLIST_BLOCK_SIZE +
                      (size_t)index * R6_LOADLIST_STREAM_SIZE);
}

int r6_loadlist_stream(const void *data, size_t size, uint32_t index,
                       r6_loadlist_stream_t *out) {
    const unsigned char *bytes;
    r6_loadlist_header_t header;
    r6_loadlist_block_t block;
    uint32_t owner = 0;
    uint32_t row;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.stream_count || !out) {
        return R6_ERR_ARG;
    }
    result = loadlist_owner(data, size, index, &owner);
    if (result != R6_OK) {
        return result;
    }
    result = r6_loadlist_block(data, size, owner, &block);
    if (result != R6_OK) {
        return result;
    }
    bytes = (const unsigned char *)data;
    row = loadlist_stream_row(data, size, index);
    out->offset = r6_u32(bytes, row);
    out->size = r6_u32(bytes, row + 4);
    if (out->size < R6_LOADLIST_MIN_STREAM ||
            out->offset > block.inflated_size ||
            out->size > block.inflated_size - out->offset) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_loadlist_stream_name(const void *data, size_t size, uint32_t index,
                            char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_loadlist_header_t header;
    uint32_t row;
    int result = loadlist_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.stream_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = loadlist_stream_row(data, size, index);
    return loadlist_string(data, size, r6_u32(bytes, row + 8), out, capacity);
}
