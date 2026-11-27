/* Bounds-checked reader for the packed .MED header facts. No animation data is
 * read or interpreted; only validated header words and paths are copied. */

#include "r6/r6_med_headers.h"

#include "core/internal.h"

enum {
    R6_MED_HEADER_SIZE = 24,
    R6_MED_RECORD_SIZE = 44,
    R6_MED_HEADER_OFF = 0x100
};

static const unsigned char med_magic[8] = {
    'R', '6', 'M', 'E', 'D', 0, 1, 0
};

static int med_layout(const void *data, size_t size, r6_med_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_med_header header;
    uint32_t count;
    size_t records;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_MED_HEADER_SIZE ||
            r6_memcmp(bytes, med_magic, sizeof(med_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u ||
            r6_u32(bytes, 16) != R6_MED_HEADER_OFF) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 12);
    if (count > ((size_t)-1 - R6_MED_HEADER_SIZE) / R6_MED_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    records = (size_t)count * R6_MED_RECORD_SIZE;
    header.strings_size = r6_u32(bytes, 20);
    if ((size_t)R6_MED_HEADER_SIZE + records > size ||
            (size_t)header.strings_size !=
            size - R6_MED_HEADER_SIZE - records) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.count = count;
    header.header_off = R6_MED_HEADER_OFF;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int med_row_at(const void *data, size_t size, uint32_t index,
                      const unsigned char **bytes, size_t *row_off,
                      uint32_t *strings_size) {
    r6_med_header header;
    int result = med_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = R6_MED_HEADER_SIZE + (size_t)index * R6_MED_RECORD_SIZE;
    *strings_size = header.strings_size;
    return R6_OK;
}

int r6_med_parse(const void *data, size_t size, r6_med_header *out) {
    return med_layout(data, size, out);
}

int r6_med_row(const void *data, size_t size, uint32_t index,
               r6_med_row_t *out) {
    const unsigned char *bytes;
    size_t row;
    uint32_t strings_size;
    uint32_t frames;
    uint32_t file_size;
    int result = med_row_at(data, size, index, &bytes, &row, &strings_size);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    frames = r6_u32(bytes, row + 16);
    file_size = r6_u32(bytes, row + 8);
    if (r6_u32(bytes, row + 12) != 0u || r6_u32(bytes, row + 20) != 408u ||
            r6_u32(bytes, row + 24) != 2560u ||
            r6_u32(bytes, row + 32) != 76u ||
            frames > 0xffffffffu / 480u ||
            r6_u32(bytes, row + 28) != frames * 480u ||
            r6_u32(bytes, row + 36) != frames * 60u ||
            r6_u32(bytes, row + 40) != file_size) {
        return R6_ERR_FORMAT;
    }
    out->file_size = file_size;
    out->frames = frames;
    out->word0 = r6_u32(bytes, row + 12);
    out->word2 = r6_u32(bytes, row + 20);
    out->word3 = r6_u32(bytes, row + 24);
    out->word4 = r6_u32(bytes, row + 28);
    out->word5 = r6_u32(bytes, row + 32);
    out->word6 = r6_u32(bytes, row + 36);
    out->word7 = r6_u32(bytes, row + 40);
    return R6_OK;
}

int r6_med_path(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    size_t strings_off;
    uint32_t strings_size;
    uint32_t offset;
    uint32_t length;
    size_t at;
    int result = med_row_at(data, size, index, &bytes, &row, &strings_size);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_MED_HEADER_SIZE +
                  (size_t)r6_u32(bytes, 12) * R6_MED_RECORD_SIZE;
    offset = r6_u32(bytes, row);
    length = r6_u32(bytes, row + 4);
    if (!length || offset > strings_size ||
            length > strings_size - offset ||
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
