/* Bounds-checked reader for packed .MTMP facts. Only copied strings cross the
 * bridge; no object naming, parent or transform meaning is interpreted. */

#include "r6/r6_mtmp.h"

#include "core/internal.h"

enum {
    R6_MTMP_HEADER_SIZE = 24,
    R6_MTMP_FILE_SIZE = 24,
    R6_MTMP_OBJECT_SIZE = 8
};

static const unsigned char mtmp_magic[8] = {
    'R', '6', 'M', 'T', 'M', 'P', 0, 1
};

static int mtmp_layout(const void *data, size_t size, r6_mtmp_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_mtmp_header_t header;
    size_t files;
    size_t objects;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_MTMP_HEADER_SIZE ||
            r6_memcmp(bytes, mtmp_magic, sizeof(mtmp_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.file_count = r6_u32(bytes, 12);
    header.object_count = r6_u32(bytes, 16);
    if (header.file_count > ((size_t)-1 - R6_MTMP_HEADER_SIZE) /
                            R6_MTMP_FILE_SIZE ||
            header.object_count > ((size_t)-1 - R6_MTMP_HEADER_SIZE -
                                   (size_t)header.file_count *
                                   R6_MTMP_FILE_SIZE) / R6_MTMP_OBJECT_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_MTMP_FILE_SIZE;
    objects = (size_t)header.object_count * R6_MTMP_OBJECT_SIZE;
    header.strings_size = r6_u32(bytes, 20);
    if (!header.file_count || !header.object_count ||
            !header.strings_size ||
            (size_t)R6_MTMP_HEADER_SIZE + files + objects >
            size || (size_t)R6_MTMP_HEADER_SIZE + files + objects +
            header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int mtmp_row(const void *data, size_t size, uint32_t index,
                    const unsigned char **bytes, size_t *row_off) {
    r6_mtmp_header_t header;
    int result = mtmp_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = R6_MTMP_HEADER_SIZE + (size_t)index * R6_MTMP_FILE_SIZE;
    return R6_OK;
}

static int mtmp_string(const void *data, size_t size, uint32_t offset,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_mtmp_header_t header;
    size_t strings_off;
    size_t end;
    uint32_t at;
    if (mtmp_layout(data, size, &header) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_MTMP_HEADER_SIZE +
                  (size_t)header.file_count * R6_MTMP_FILE_SIZE +
                  (size_t)header.object_count * R6_MTMP_OBJECT_SIZE;
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

int r6_mtmp_parse(const void *data, size_t size, r6_mtmp_header_t *out) {
    return mtmp_layout(data, size, out);
}

int r6_mtmp_file(const void *data, size_t size, uint32_t index,
                 r6_mtmp_file_t *out) {
    const unsigned char *bytes;
    size_t row;
    r6_mtmp_header_t header;
    int result = mtmp_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!out || mtmp_layout(data, size, &header) != R6_OK) {
        return R6_ERR_ARG;
    }
    out->file_size = r6_u32(bytes, row + 8);
    out->object_first = r6_u32(bytes, row + 16);
    out->object_count = r6_u32(bytes, row + 20);
    if (!out->file_size ||
            out->object_first > header.object_count ||
            out->object_count > header.object_count - out->object_first) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static uint32_t mtmp_text_off(const void *data, size_t size, uint32_t relative) {
    r6_mtmp_header_t header;
    if (mtmp_layout(data, size, &header) != R6_OK) {
        return 0;
    }
    return (uint32_t)(R6_MTMP_HEADER_SIZE +
                      (size_t)header.file_count * R6_MTMP_FILE_SIZE +
                      (size_t)header.object_count * R6_MTMP_OBJECT_SIZE +
                      relative);
}

int r6_mtmp_path(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    int result = mtmp_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    return mtmp_string(data, size, mtmp_text_off(data, size,
                                                r6_u32(bytes, row)),
                       out, capacity);
}

int r6_mtmp_scale(const void *data, size_t size, uint32_t index,
                  char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    int result = mtmp_row(data, size, index, &bytes, &row);
    if (result != R6_OK) {
        return result;
    }
    return mtmp_string(data, size, mtmp_text_off(data, size,
                                                r6_u32(bytes, row + 12)),
                       out, capacity);
}

int r6_mtmp_object(const void *data, size_t size, uint32_t index,
                   char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_mtmp_header_t header;
    uint32_t record;
    int result = mtmp_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.object_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    record = (uint32_t)(R6_MTMP_HEADER_SIZE +
                        (size_t)header.file_count * R6_MTMP_FILE_SIZE +
                        (size_t)index * R6_MTMP_OBJECT_SIZE);
    return mtmp_string(data, size, mtmp_text_off(data, size,
                                                r6_u32(bytes, record)),
                       out, capacity);
}
