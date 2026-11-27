/* Bounds-checked reader for packed XMD.001 asset header facts. No asset
 * payload is opened or interpreted; only copied numbers and paths cross. */

#include "r6/r6_xmd_asset_catalog.h"

#include "core/internal.h"

enum {
    R6_XMD_ASSET_HEADER_SIZE = 24,
    R6_XMD_ASSET_FILE_SIZE = 52,
    R6_XMD_ASSET_STREAM_SIZE = 8,
    R6_XMD_ASSET_TABLE_HEAD = 16
};

static const unsigned char xmd_asset_magic[8] = {
    'R', '6', 'X', 'A', 'S', 0, 1, 0
};

static int xmd_asset_layout(const void *data, size_t size,
                            r6_xmd_asset_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmd_asset_header_t header;
    size_t files;
    size_t streams;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_XMD_ASSET_HEADER_SIZE ||
            r6_memcmp(bytes, xmd_asset_magic, sizeof(xmd_asset_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.file_count = r6_u32(bytes, 12);
    header.stream_count = r6_u32(bytes, 16);
    if (!header.file_count || !header.stream_count ||
            header.file_count > ((size_t)-1 - R6_XMD_ASSET_HEADER_SIZE) /
                                R6_XMD_ASSET_FILE_SIZE ||
            header.stream_count > ((size_t)-1 - R6_XMD_ASSET_HEADER_SIZE -
                                   (size_t)header.file_count *
                                   R6_XMD_ASSET_FILE_SIZE) /
                                  R6_XMD_ASSET_STREAM_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_XMD_ASSET_FILE_SIZE;
    streams = (size_t)header.stream_count * R6_XMD_ASSET_STREAM_SIZE;
    header.strings_size = r6_u32(bytes, 20);
    if (!header.strings_size ||
            (size_t)R6_XMD_ASSET_HEADER_SIZE + files + streams > size ||
            (size_t)R6_XMD_ASSET_HEADER_SIZE + files + streams +
            header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int xmd_asset_row(const void *data, size_t size, uint32_t index,
                         const unsigned char **bytes, size_t *row_off) {
    r6_xmd_asset_header_t header;
    int result = xmd_asset_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = R6_XMD_ASSET_HEADER_SIZE +
               (size_t)index * R6_XMD_ASSET_FILE_SIZE;
    return R6_OK;
}

static int xmd_asset_string(const void *data, size_t size, uint32_t offset,
                            char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmd_asset_header_t header;
    size_t strings_off;
    size_t end;
    uint32_t at;
    int result = xmd_asset_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_XMD_ASSET_HEADER_SIZE +
                  (size_t)header.file_count * R6_XMD_ASSET_FILE_SIZE +
                  (size_t)header.stream_count * R6_XMD_ASSET_STREAM_SIZE;
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

int r6_xmd_asset_parse(const void *data, size_t size,
                       r6_xmd_asset_header_t *out) {
    return xmd_asset_layout(data, size, out);
}

int r6_xmd_asset_file(const void *data, size_t size, uint32_t index,
                      r6_xmd_asset_file_t *out) {
    const unsigned char *bytes;
    size_t row;
    r6_xmd_asset_header_t header;
    int result = xmd_asset_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out || xmd_asset_layout(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    out->source_size = r6_u32(bytes, row + 16);
    out->inflated_size = r6_u32(bytes, row + 20);
    out->ext = r6_u32(bytes, row + 8);
    out->wrap = r6_u32(bytes, row + 12);
    out->gzip_flags = r6_u32(bytes, row + 24);
    out->gzip_mtime = r6_u32(bytes, row + 28);
    out->gzip_xfl_os = r6_u32(bytes, row + 32);
    out->expected_size = r6_u32(bytes, row + 36);
    out->xmd_version = r6_u32(bytes, row + 40);
    out->stream_first = r6_u32(bytes, row + 44);
    out->stream_count = r6_u32(bytes, row + 48);
    if (!out->source_size || !out->inflated_size ||
            (out->ext != R6_XMD_ASSET_EXT_TEX &&
             out->ext != R6_XMD_ASSET_EXT_MDL) ||
            (out->wrap != R6_XMD_ASSET_WRAP_RAW &&
             out->wrap != R6_XMD_ASSET_WRAP_GZIP) ||
            out->xmd_version != R6_XMD_ASSET_VERSION ||
            !out->stream_count ||
            out->stream_first > header.stream_count ||
            out->stream_count > header.stream_count - out->stream_first) {
        return R6_ERR_FORMAT;
    }
    if (index + 1u < header.file_count) {
        uint32_t next_first = r6_u32(bytes, row + R6_XMD_ASSET_FILE_SIZE + 44);
        if (out->stream_first > next_first ||
                next_first - out->stream_first != out->stream_count) {
            return R6_ERR_FORMAT;
        }
    } else if (out->stream_first != header.stream_count - out->stream_count) {
        return R6_ERR_FORMAT;
    }
    if (out->wrap == R6_XMD_ASSET_WRAP_RAW) {
        if (out->gzip_flags || out->gzip_mtime || out->gzip_xfl_os ||
                out->expected_size) {
            return R6_ERR_FORMAT;
        }
    } else if (out->expected_size != out->inflated_size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_xmd_asset_path(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    int result = xmd_asset_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    return xmd_asset_string(data, size, r6_u32(bytes, row), out, capacity);
}

int r6_xmd_asset_stream(const void *data, size_t size, uint32_t index,
                        uint32_t local, uint32_t *offset, uint32_t *size_out) {
    const unsigned char *bytes;
    r6_xmd_asset_header_t header;
    r6_xmd_asset_file_t file;
    uint32_t at;
    uint32_t first_offset;
    uint32_t boundary;
    uint32_t got_offset;
    uint32_t got_size;
    uint32_t previous;
    int result = xmd_asset_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!offset || !size_out) {
        return R6_ERR_ARG;
    }
    result = r6_xmd_asset_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    if (local >= file.stream_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    at = (uint32_t)(R6_XMD_ASSET_HEADER_SIZE +
                    (size_t)header.file_count * R6_XMD_ASSET_FILE_SIZE +
                    (size_t)(file.stream_first + local) *
                    R6_XMD_ASSET_STREAM_SIZE);
    first_offset = r6_u32(bytes, (uint32_t)(R6_XMD_ASSET_HEADER_SIZE +
                        (size_t)header.file_count * R6_XMD_ASSET_FILE_SIZE +
                        (size_t)file.stream_first * R6_XMD_ASSET_STREAM_SIZE));
    if (first_offset < R6_XMD_ASSET_TABLE_HEAD + 4u * file.stream_count ||
            first_offset > file.inflated_size) {
        return R6_ERR_FORMAT;
    }
    if (local + 1 < file.stream_count) {
        boundary = r6_u32(bytes, at + R6_XMD_ASSET_STREAM_SIZE);
    } else {
        boundary = file.inflated_size;
    }
    got_offset = r6_u32(bytes, at);
    got_size = r6_u32(bytes, at + 4);
    if (local) {
        previous = r6_u32(bytes, at - R6_XMD_ASSET_STREAM_SIZE);
        if (previous > got_offset) {
            return R6_ERR_FORMAT;
        }
    }
    if (got_offset > boundary || boundary > file.inflated_size ||
            got_size != boundary - got_offset ||
            got_offset < R6_XMD_ASSET_TABLE_HEAD + 4u * file.stream_count) {
        return R6_ERR_FORMAT;
    }
    *offset = got_offset;
    *size_out = got_size;
    return R6_OK;
}
