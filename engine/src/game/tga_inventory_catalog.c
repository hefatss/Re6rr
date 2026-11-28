/* Bounds-checked reader for packed TGA header facts. Only copied paths,
 * header words and size facts cross the bridge. */

#include "r6/r6_tga_inventory_catalog.h"

#include "core/internal.h"

enum {
    R6_TGA_HEADER_SIZE = 36,
    R6_TGA_FILE_SIZE = 40,
    R6_TGA_PREFIX = 18,
    R6_TGA_FOOTER = 26
};

static const unsigned char tga_magic[8] = {
    'R', '6', 'T', 'G', 'A', 0, 1, 0
};

static size_t tga_string_base(const r6_tga_inventory_header_t *header) {
    return R6_TGA_HEADER_SIZE + (size_t)header->file_count * R6_TGA_FILE_SIZE;
}

static int tga_header(const void *data, size_t size,
                      r6_tga_inventory_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tga_inventory_header_t header;
    size_t files;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_TGA_HEADER_SIZE ||
            r6_memcmp(bytes, tga_magic, sizeof(tga_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.string_size = r6_u32(bytes, 16);
    header.total_bytes = r6_u32(bytes, 20);
    header.raw_count = r6_u32(bytes, 24);
    header.rle_count = r6_u32(bytes, 28);
    header.footer_count = r6_u32(bytes, 32);
    if (!header.file_count || !header.string_size || !header.total_bytes ||
            header.raw_count + header.rle_count != header.file_count ||
            header.footer_count != header.file_count ||
            header.file_count >
            ((size_t)-1 - R6_TGA_HEADER_SIZE) / R6_TGA_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_TGA_FILE_SIZE;
    base = R6_TGA_HEADER_SIZE + files;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int tga_validate_string(const void *data,
                               const r6_tga_inventory_header_t *header,
                               uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = tga_string_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!length || (size_t)offset < base || (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (bytes[(size_t)offset + at] >= 0x80u) {
            return R6_ERR_FORMAT;
        }
    }
    if (bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int tga_file_row(const void *data, const r6_tga_inventory_header_t *h,
                        uint32_t index, r6_tga_inventory_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tga_inventory_file_t file;
    size_t row = R6_TGA_HEADER_SIZE + (size_t)index * R6_TGA_FILE_SIZE;
    uint64_t minimum;
    int result = tga_validate_string(data, h, r6_u32(bytes, row),
                                     r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(&file, bytes + row, sizeof(file));
    if (!file.width || !file.height || !file.pixels ||
            (file.bpp != 24u && file.bpp != 32u) ||
            (file.kind != 2u && file.kind != 10u) ||
            (file.descriptor & 0xf0u) || file.raw_exact > 1u ||
            file.path_length < 4 ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".tga", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    minimum = R6_TGA_PREFIX + (uint64_t)file.width * file.height *
              (file.bpp / 8u) + R6_TGA_FOOTER;
    if (file.pixels != file.width * file.height * (file.bpp / 8u) ||
            file.size < R6_TGA_PREFIX + R6_TGA_FOOTER ||
            (file.descriptor & 0x0fu) != (file.bpp == 32u ? 8u : 0u)) {
        return R6_ERR_FORMAT;
    }
    if ((file.kind == 2u && (uint64_t)file.size != minimum) ||
            (file.kind == 10u && (uint64_t)file.size >= minimum) ||
            file.raw_exact != (file.kind == 2u ? 1u : 0u)) {
        return R6_ERR_FORMAT;
    }
    if (out) {
        r6_memcpy(out, &file, sizeof(file));
    }
    return R6_OK;
}

static int tga_layout(const void *data, size_t size,
                      r6_tga_inventory_header_t *out) {
    r6_tga_inventory_header_t header;
    uint32_t total = 0;
    uint32_t raw = 0;
    uint32_t rle = 0;
    uint32_t at;
    int result;
    if (!out) {
        return R6_ERR_ARG;
    }
    result = tga_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_tga_inventory_file_t file;
        result = tga_file_row(data, &header, at, &file);
        if (result != R6_OK) {
            return result;
        }
        total += file.size;
        if (file.kind == 2u) {
            raw++;
        } else {
            rle++;
        }
    }
    if (total != header.total_bytes || raw != header.raw_count ||
            rle != header.rle_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_tga_inventory_parse(const void *data, size_t size,
                           r6_tga_inventory_header_t *out) {
    return tga_layout(data, size, out);
}

int r6_tga_inventory_file(const void *data, size_t size, uint32_t index,
                          r6_tga_inventory_file_t *out) {
    r6_tga_inventory_header_t header;
    int result = tga_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    return tga_file_row(data, &header, index, out);
}

int r6_tga_inventory_path(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tga_inventory_header_t header;
    size_t row;
    int result = tga_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    row = R6_TGA_HEADER_SIZE + (size_t)index * R6_TGA_FILE_SIZE;
    result = tga_validate_string(data, &header, r6_u32(bytes, row),
                                 r6_u32(bytes, row + 4));
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)r6_u32(bytes, row + 4) + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + r6_u32(bytes, row), r6_u32(bytes, row + 4));
    out[r6_u32(bytes, row + 4)] = 0;
    return R6_OK;
}
