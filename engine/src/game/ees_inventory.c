/* Bounds-checked reader for packed .EES header facts. No scene bytes are
 * opened or interpreted; only arithmetic on copied numbers is rechecked. */

#include "r6/r6_ees_inventory.h"

#include "core/internal.h"

enum {
    R6_EES_HEADER_SIZE = 24,
    R6_EES_FILE_SIZE = 44,
    R6_EES_ARRAY_SIZE = 24,
    R6_EES_CAM_VERSION_0 = 0x2712,
    R6_EES_CAM_VERSION_1 = 0x2713,
    R6_EES_CAM_HEADER_0 = 0x1a8,
    R6_EES_CAM_HEADER_1 = 0x1b0,
    R6_EES_CAR_HEADER_0 = 0x1bc,
    R6_EES_CAR_HEADER_1 = 0x1c8
};

static const unsigned char ees_magic[8] = {
    'R', '6', 'E', 'E', 'S', 'I', 0, 1
};

static int ees_layout(const void *data, size_t size,
                      r6_ees_inventory_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ees_inventory_header_t header;
    size_t files;
    size_t arrays;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_EES_HEADER_SIZE ||
            r6_memcmp(bytes, ees_magic, sizeof(ees_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.file_count = r6_u32(bytes, 12);
    header.array_count = r6_u32(bytes, 16);
    if (header.file_count > ((size_t)-1 - R6_EES_HEADER_SIZE) /
                            R6_EES_FILE_SIZE ||
            header.array_count > ((size_t)-1 - R6_EES_HEADER_SIZE -
                                  (size_t)header.file_count *
                                  R6_EES_FILE_SIZE) / R6_EES_ARRAY_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_EES_FILE_SIZE;
    arrays = (size_t)header.array_count * R6_EES_ARRAY_SIZE;
    header.strings_size = r6_u32(bytes, 20);
    if (!header.file_count || !header.array_count || !header.strings_size ||
            (size_t)R6_EES_HEADER_SIZE + files + arrays > size ||
            (size_t)R6_EES_HEADER_SIZE + files + arrays +
            header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int ees_file_row(const void *data, size_t size, uint32_t index,
                        const unsigned char **bytes, size_t *row_off,
                        r6_ees_inventory_header_t *header) {
    int result = ees_layout(data, size, header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header->file_count) {
        return R6_ERR_ARG;
    }
    *bytes = (const unsigned char *)data;
    *row_off = R6_EES_HEADER_SIZE + (size_t)index * R6_EES_FILE_SIZE;
    return R6_OK;
}

static int ees_string(const void *data, size_t size, uint32_t offset,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ees_inventory_header_t header;
    size_t strings_off;
    size_t end;
    uint32_t at;
    int result = ees_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_EES_HEADER_SIZE +
                  (size_t)header.file_count * R6_EES_FILE_SIZE +
                  (size_t)header.array_count * R6_EES_ARRAY_SIZE;
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

static uint32_t ees_text_off(const void *data, size_t size, uint32_t relative) {
    r6_ees_inventory_header_t header;
    if (ees_layout(data, size, &header) != R6_OK) {
        return 0;
    }
    return (uint32_t)(R6_EES_HEADER_SIZE +
                      (size_t)header.file_count * R6_EES_FILE_SIZE +
                      (size_t)header.array_count * R6_EES_ARRAY_SIZE +
                      relative);
}

int r6_ees_inventory_parse(const void *data, size_t size,
                           r6_ees_inventory_header_t *out) {
    return ees_layout(data, size, out);
}

int r6_ees_inventory_file(const void *data, size_t size, uint32_t index,
                          r6_ees_inventory_file_t *out) {
    const unsigned char *bytes;
    size_t row;
    r6_ees_inventory_header_t header;
    int result = ees_file_row(data, size, index, &bytes, &row, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    out->file_size = r6_u32(bytes, row + 8);
    out->kind = r6_u32(bytes, row + 12);
    out->version = r6_u32(bytes, row + 16);
    out->count = r6_u32(bytes, row + 20);
    out->effect_count = r6_u32(bytes, row + 24);
    out->header_size = r6_u32(bytes, row + 28);
    out->array_first = r6_u32(bytes, row + 32);
    out->array_count = r6_u32(bytes, row + 36);
    if (out->array_first > header.array_count ||
            out->array_count > header.array_count - out->array_first) {
        return R6_ERR_FORMAT;
    }
    if (out->kind == R6_EES_INVENTORY_KIND_CAM) {
        if ((out->version != R6_EES_CAM_VERSION_0 &&
             out->version != R6_EES_CAM_VERSION_1) ||
                out->effect_count != 0 ||
                (out->header_size != R6_EES_CAM_HEADER_0 &&
                 out->header_size != R6_EES_CAM_HEADER_1) ||
                out->array_count != 2) {
            return R6_ERR_FORMAT;
        }
    } else if (out->kind == R6_EES_INVENTORY_KIND_CAR) {
        if (out->version != R6_EES_CAM_VERSION_0 ||
                (out->header_size != R6_EES_CAR_HEADER_0 &&
                 out->header_size != R6_EES_CAR_HEADER_1) ||
                out->array_count != 3) {
            return R6_ERR_FORMAT;
        }
    } else {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_ees_inventory_path(const void *data, size_t size, uint32_t index,
                          char *out, size_t capacity) {
    const unsigned char *bytes;
    size_t row;
    r6_ees_inventory_header_t header;
    int result = ees_file_row(data, size, index, &bytes, &row, &header);
    if (result != R6_OK) {
        return result;
    }
    return ees_string(data, size, ees_text_off(data, size,
                                              r6_u32(bytes, row)),
                      out, capacity);
}

int r6_ees_inventory_array(const void *data, size_t size, uint32_t index,
                           char *name, size_t capacity,
                           r6_ees_inventory_array_t *out) {
    const unsigned char *bytes;
    r6_ees_inventory_header_t header;
    r6_ees_inventory_file_t file;
    uint32_t record;
    uint32_t local;
    uint32_t owner = 0;
    uint64_t expected_offset;
    uint64_t expected_size;
    uint32_t expected_count;
    uint32_t expected_stride;
    const char *expected_name;
    int result = ees_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.array_count || !out || !name) {
        return R6_ERR_ARG;
    }
    for (; owner < header.file_count; owner++) {
        result = r6_ees_inventory_file(data, size, owner, &file);
        if (result != R6_OK) {
            return result;
        }
        if (index >= file.array_first &&
                index - file.array_first < file.array_count) {
            break;
        }
    }
    if (owner == header.file_count) {
        return R6_ERR_FORMAT;
    }
    local = index - file.array_first;
    if (file.kind == R6_EES_INVENTORY_KIND_CAM) {
        if (local == 0) {
            expected_name = "camera_info";
            expected_count = file.count;
            expected_stride = 0x50;
            expected_offset = file.header_size;
        } else {
            expected_name = "camera_data";
            expected_count = file.count;
            expected_stride = 0x160;
            expected_offset = (uint64_t)file.header_size +
                              (uint64_t)file.count * 0x50u;
        }
        expected_size = (uint64_t)expected_count * expected_stride;
    } else {
        uint64_t disp = (uint64_t)file.count * 0x180u;
        uint64_t effect = (uint64_t)file.effect_count * 0xa0u;
        if (local == 0) {
            expected_name = "car_disp";
            expected_count = file.count;
            expected_stride = 0x180;
            expected_offset = file.header_size;
            expected_size = disp;
        } else if (local == 1) {
            expected_name = "car_effect";
            expected_count = file.effect_count;
            expected_stride = 0xa0;
            expected_offset = (uint64_t)file.header_size + disp;
            expected_size = effect;
        } else {
            expected_name = "car_info";
            expected_count = file.count;
            expected_stride = 0x8c;
            expected_offset = (uint64_t)file.header_size + disp + effect;
            expected_size = (uint64_t)file.count * 0x8cu;
        }
    }
    bytes = (const unsigned char *)data;
    record = (uint32_t)(R6_EES_HEADER_SIZE +
                        (size_t)header.file_count * R6_EES_FILE_SIZE +
                        (size_t)index * R6_EES_ARRAY_SIZE);
    out->count = r6_u32(bytes, record + 8);
    out->stride = r6_u32(bytes, record + 12);
    out->offset = r6_u32(bytes, record + 16);
    out->size = r6_u32(bytes, record + 20);
    if (out->count != expected_count || out->stride != expected_stride ||
            out->offset != expected_offset || out->size != expected_size ||
            expected_offset > file.file_size || expected_size > file.file_size ||
            expected_offset > file.file_size - expected_size) {
        return R6_ERR_FORMAT;
    }
    if (r6_strlen(expected_name) + 1 > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(name, expected_name, r6_strlen(expected_name) + 1);
    return R6_OK;
}
