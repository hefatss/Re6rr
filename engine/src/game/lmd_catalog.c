/* Bounds-checked reader for packed .LMD header facts. The gzip payload and XMD
 * stream bytes are not read; only invariant checks on copied numbers happen. */

#include "r6/r6_lmd_catalog.h"

#include "core/internal.h"

enum {
    R6_LMD_HEADER_SIZE = 24,
    R6_LMD_FILE_SIZE = 40,
    R6_LMD_STREAM_SIZE = 8
};

static const unsigned char lmd_magic[8] = {
    'R', '6', 'L', 'M', 'D', 0, 1, 0
};

static int lmd_layout(const void *data, size_t size, r6_lmd_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_lmd_header_t header;
    size_t records;
    size_t streams;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_LMD_HEADER_SIZE ||
            r6_memcmp(bytes, lmd_magic, sizeof(lmd_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u ||
            r6_u32(bytes, 12) != R6_LMD_FILES ||
            r6_u32(bytes, 16) != R6_LMD_STREAMS_PER_FILE) {
        return R6_ERR_FORMAT;
    }
    records = (size_t)R6_LMD_FILES * R6_LMD_FILE_SIZE;
    streams = (size_t)R6_LMD_FILES * R6_LMD_STREAMS_PER_FILE *
              R6_LMD_STREAM_SIZE;
    header.strings_size = r6_u32(bytes, 20);
    if ((size_t)R6_LMD_HEADER_SIZE + records + streams > size ||
            (size_t)R6_LMD_HEADER_SIZE + records + streams +
            header.strings_size != size || !header.strings_size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = R6_LMD_FILES;
    header.stream_count = R6_LMD_STREAMS_PER_FILE;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int lmd_row(const void *data, size_t size, uint32_t index,
                   const unsigned char **bytes, size_t *row_off) {
    r6_lmd_header_t header;
    int result = lmd_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = R6_LMD_HEADER_SIZE + (size_t)index * R6_LMD_FILE_SIZE;
    return R6_OK;
}

int r6_lmd_parse(const void *data, size_t size, r6_lmd_header_t *out) {
    return lmd_layout(data, size, out);
}

int r6_lmd_file(const void *data, size_t size, uint32_t index,
                r6_lmd_file_t *out) {
    const unsigned char *bytes;
    size_t row;
    int result = lmd_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    out->compressed_size = r6_u32(bytes, row + 8);
    out->gzip_flags = r6_u32(bytes, row + 12);
    out->gzip_mtime = r6_u32(bytes, row + 16);
    out->gzip_xfl_os = r6_u32(bytes, row + 20);
    out->expected_size = r6_u32(bytes, row + 24);
    out->inflated_size = r6_u32(bytes, row + 28);
    out->xmd_version = r6_u32(bytes, row + 32);
    out->stream_first = r6_u32(bytes, row + 36);
    if (out->compressed_size < 18u || out->gzip_flags > 255u ||
            out->gzip_xfl_os > 0xffffu ||
            out->expected_size != out->inflated_size ||
            out->inflated_size < R6_LMD_XMD_HEADER ||
            out->xmd_version != 1u ||
            out->stream_first != index * R6_LMD_STREAMS_PER_FILE) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_lmd_path(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    size_t strings_off = R6_LMD_HEADER_SIZE +
                         (size_t)R6_LMD_FILES * R6_LMD_FILE_SIZE +
                         (size_t)R6_LMD_FILES * R6_LMD_STREAMS_PER_FILE *
                         R6_LMD_STREAM_SIZE;
    r6_lmd_header_t header;
    uint32_t offset;
    uint32_t length;
    size_t at;
    int result = lmd_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out || lmd_layout(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, row);
    length = r6_u32(bytes, row + 4);
    if (!length || offset > header.strings_size ||
            length > header.strings_size - offset ||
            bytes[strings_off + offset + length]) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (!bytes[strings_off + offset + at]) {
            return R6_ERR_FORMAT;
        }
    }
    if (capacity <= length) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + strings_off + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_lmd_stream(const void *data, size_t size, uint32_t index,
                  uint32_t local, uint32_t *offset_out, uint32_t *size_out) {
    const unsigned char *bytes;
    size_t row;
    size_t stream_off;
    uint32_t offset;
    uint32_t stored;
    uint32_t next;
    r6_lmd_file_t file;
    int result = lmd_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    if (local >= R6_LMD_STREAMS_PER_FILE) {
        return R6_ERR_ARG;
    }
    result = r6_lmd_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    stream_off = R6_LMD_HEADER_SIZE +
                 (size_t)R6_LMD_FILES * R6_LMD_FILE_SIZE +
                 (size_t)file.stream_first * R6_LMD_STREAM_SIZE +
                 (size_t)local * R6_LMD_STREAM_SIZE;
    offset = r6_u32(bytes, stream_off);
    stored = r6_u32(bytes, stream_off + 4);
    next = local + 1 < R6_LMD_STREAMS_PER_FILE
               ? r6_u32(bytes, stream_off + R6_LMD_STREAM_SIZE)
               : file.inflated_size;
    if (offset < R6_LMD_XMD_HEADER || offset > file.inflated_size ||
            next < offset || next > file.inflated_size || stored != next - offset) {
        return R6_ERR_FORMAT;
    }
    if (offset_out) {
        *offset_out = offset;
    }
    if (size_out) {
        *size_out = stored;
    }
    return R6_OK;
}
