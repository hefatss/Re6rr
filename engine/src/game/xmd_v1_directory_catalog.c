/* Bounds-checked reader for packed XMD version 0/1 stream directories. */

#include "r6/r6_xmd_v1_directory_catalog.h"

#include "core/internal.h"

enum {
    R6_XD1_HEADER_SIZE = 28,
    R6_XD1_FILE_SIZE = 28,
    R6_XD1_STREAM_SIZE = 16,
    R6_XD1_FILES = 3,
    R6_XD1_STREAMS = 30,
    R6_XD1_SOURCE = 527072,
    R6_XD1_MAX_STRING = 96
};

static const unsigned char xd1_magic[8] = {
    'R', '6', 'X', 'D', '1', 0, 1, 0
};

static int xd1_header(const void *data, size_t size,
                      r6_xmd_v1_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmd_v1_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_XD1_HEADER_SIZE ||
            r6_memcmp(bytes, xd1_magic, sizeof(xd1_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_XD1_FILES ||
            r6_u32(bytes, 16) != R6_XD1_STREAMS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_XD1_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.stream_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_XD1_HEADER_SIZE +
           (size_t)header.file_count * R6_XD1_FILE_SIZE +
           (size_t)header.stream_count * R6_XD1_STREAM_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t xd1_streams_base(void) {
    return R6_XD1_HEADER_SIZE + R6_XD1_FILES * R6_XD1_FILE_SIZE;
}

static size_t xd1_strings_base(void) {
    return xd1_streams_base() + R6_XD1_STREAMS * R6_XD1_STREAM_SIZE;
}

static int xd1_string(const void *data,
                      const r6_xmd_v1_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = xd1_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_XD1_MAX_STRING || (size_t)offset < base ||
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

static int xd1_file(const void *data, size_t size, uint32_t index,
                    r6_xmd_v1_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmd_v1_header_t header;
    r6_xmd_v1_file_t file;
    size_t at;
    uint32_t table_end;
    int result = xd1_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_XD1_HEADER_SIZE + (size_t)index * R6_XD1_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || file.version > 1u || !file.count ||
            file.stream_index > header.stream_count ||
            file.count > header.stream_count - file.stream_index ||
            file.path_length < 4 ||
            xd1_string(data, &header, file.path_offset,
                       file.path_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    table_end = 16u + file.count * 4u;
    if (file.table_end != table_end) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int xd1_stream(const void *data,
                      const r6_xmd_v1_header_t *header,
                      uint32_t index, r6_xmd_v1_stream_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmd_v1_stream_t stream;
    size_t at = xd1_streams_base() + (size_t)index * R6_XD1_STREAM_SIZE;
    if (index >= header->stream_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&stream, bytes + at, sizeof(stream));
    (void)bytes;
    r6_memcpy(out, &stream, sizeof(stream));
    return R6_OK;
}

int r6_xmd_v1_parse(const void *data, size_t size, r6_xmd_v1_header_t *out) {
    r6_xmd_v1_header_t header;
    r6_xmd_v1_file_t file;
    r6_xmd_v1_stream_t stream;
    uint32_t source = 0;
    uint32_t next = 0;
    uint32_t at;
    int result = xd1_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        uint32_t index;
        uint32_t end = 0;
        result = xd1_file(data, size, at, &file);
        if (result != R6_OK || file.stream_index != next) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        next += file.count;
        for (index = 0; index < file.count; index++) {
            result = xd1_stream(data, &header, file.stream_index + index,
                                &stream);
            if (result != R6_OK) {
                return result;
            }
            if (stream.offset < file.table_end || stream.offset > file.size ||
                    stream.length > file.size - stream.offset) {
                return R6_ERR_FORMAT;
            }
            if (index && stream.offset != end) {
                return R6_ERR_FORMAT;
            }
            end = stream.offset + stream.length;
        }
        if (end > file.size) {
            return R6_ERR_FORMAT;
        }
    }
    if (source != header.source_bytes || next != header.stream_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_xmd_v1_file(const void *data, size_t size, uint32_t index,
                   r6_xmd_v1_file_t *out) {
    return xd1_file(data, size, index, out);
}

int r6_xmd_v1_path(const void *data, size_t size, uint32_t index,
                   char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmd_v1_header_t header;
    r6_xmd_v1_file_t file;
    int result = xd1_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = xd1_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    if (xd1_string(data, &header, file.path_offset,
                   file.path_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (!out || (size_t)file.path_length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + file.path_offset, file.path_length);
    out[file.path_length] = 0;
    return R6_OK;
}

int r6_xmd_v1_stream(const void *data, size_t size, uint32_t index,
                     r6_xmd_v1_stream_t *out) {
    r6_xmd_v1_header_t header;
    int result = xd1_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return xd1_stream(data, &header, index, out);
}
