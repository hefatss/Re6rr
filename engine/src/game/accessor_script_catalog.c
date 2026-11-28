/* Bounds-checked reader for packed Lua accessor inventories. */

#include "r6/r6_accessor_script_catalog.h"

#include "core/internal.h"

enum {
    R6_ACC_HEADER_SIZE = 28,
    R6_ACC_FILE_SIZE = 28,
    R6_ACC_FUNC_SIZE = 28,
    R6_ACC_FILES = 7,
    R6_ACC_FUNCTIONS = 155,
    R6_ACC_SOURCE = 35256,
    R6_ACC_MAX_STRING = 160
};

static const unsigned char acc_magic[8] = {
    'R', '6', 'A', 'C', 'C', 0, 1, 0
};

static const uint32_t acc_sizes[7] = {
    4183u, 6379u, 13727u, 7102u, 506u, 879u, 2480u
};

static const uint32_t acc_lines[7] = {
    180u, 266u, 406u, 281u, 15u, 31u, 111u
};

static const uint32_t acc_counts[7] = {
    32u, 38u, 22u, 48u, 1u, 9u, 5u
};

static const uint32_t acc_returns[7] = {
    32u, 46u, 60u, 49u, 1u, 9u, 20u
};

static int acc_header(const void *data, size_t size,
                      r6_accessor_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_ACC_HEADER_SIZE ||
            r6_memcmp(bytes, acc_magic, sizeof(acc_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_ACC_FILES ||
            r6_u32(bytes, 16) != R6_ACC_FUNCTIONS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_ACC_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.function_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_ACC_HEADER_SIZE +
           (size_t)header.file_count * R6_ACC_FILE_SIZE +
           (size_t)header.function_count * R6_ACC_FUNC_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t acc_funcs_base(void) {
    return R6_ACC_HEADER_SIZE + R6_ACC_FILES * R6_ACC_FILE_SIZE;
}

static size_t acc_strings_base(void) {
    return acc_funcs_base() + R6_ACC_FUNCTIONS * R6_ACC_FUNC_SIZE;
}

static int acc_string(const void *data,
                      const r6_accessor_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = acc_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_ACC_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0 ||
            (!allow_empty && !length)) {
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

static int acc_copy(const void *data,
                    const r6_accessor_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = acc_string(data, header, offset, length, 1);
    if (result != R6_OK) {
        return result;
    }
    if (!out || !capacity || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int acc_file(const void *data, size_t size, uint32_t index,
                    r6_accessor_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_header_t header;
    r6_accessor_file_t file;
    uint32_t base = 0;
    uint32_t at;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < index; at++) {
        base += acc_counts[at];
    }
    r6_memcpy(&file, bytes + R6_ACC_HEADER_SIZE +
              (size_t)index * R6_ACC_FILE_SIZE, sizeof(file));
    if (file.size != acc_sizes[index] || file.lines != acc_lines[index] ||
            file.count != acc_counts[index] ||
            file.returns != acc_returns[index] ||
            file.function_base != base || file.path_length < 8 ||
            acc_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int acc_func(const void *data,
                    const r6_accessor_header_t *header,
                    uint32_t index, r6_accessor_func_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_func_t func;
    size_t at = acc_funcs_base() + (size_t)index * R6_ACC_FUNC_SIZE;
    if (index >= header->function_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&func, bytes + at, sizeof(func));
    if (!func.name_length ||
            acc_string(data, header, func.name_offset,
                       func.name_length, 0) != R6_OK ||
            acc_string(data, header, func.args_offset,
                       func.args_length, 1) != R6_OK ||
            acc_string(data, header, func.result_offset,
                       func.result_length, 1) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &func, sizeof(func));
    return R6_OK;
}

int r6_accessor_parse(const void *data, size_t size,
                      r6_accessor_header_t *out) {
    r6_accessor_header_t header;
    r6_accessor_file_t file;
    r6_accessor_func_t func;
    uint32_t source = 0;
    uint32_t next = 0;
    uint32_t at;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = acc_file(data, size, at, &file);
        if (result != R6_OK || file.function_base != next) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        next += file.count;
    }
    if (source != header.source_bytes || next != header.function_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.function_count; at++) {
        result = acc_func(data, &header, at, &func);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_accessor_file(const void *data, size_t size, uint32_t index,
                     r6_accessor_file_t *out) {
    return acc_file(data, size, index, out);
}

int r6_accessor_path(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_header_t header;
    r6_accessor_file_t file;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = acc_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return acc_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_accessor_func(const void *data, size_t size, uint32_t index,
                     r6_accessor_func_t *out) {
    r6_accessor_header_t header;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return acc_func(data, &header, index, out);
}

int r6_accessor_name(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_header_t header;
    r6_accessor_func_t func;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = acc_func(data, &header, index, &func);
    if (result != R6_OK) {
        return result;
    }
    return acc_copy(data, &header, func.name_offset, func.name_length,
                    out, capacity);
}

int r6_accessor_args(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_header_t header;
    r6_accessor_func_t func;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = acc_func(data, &header, index, &func);
    if (result != R6_OK) {
        return result;
    }
    return acc_copy(data, &header, func.args_offset, func.args_length,
                    out, capacity);
}

int r6_accessor_result(const void *data, size_t size, uint32_t index,
                       char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_accessor_header_t header;
    r6_accessor_func_t func;
    int result = acc_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = acc_func(data, &header, index, &func);
    if (result != R6_OK) {
        return result;
    }
    return acc_copy(data, &header, func.result_offset, func.result_length,
                    out, capacity);
}
