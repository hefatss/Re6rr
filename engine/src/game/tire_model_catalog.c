/* Bounds-checked reader for packed TireInfo inventories. */

#include "r6/r6_tire_model_catalog.h"

#include "core/internal.h"

enum {
    R6_TIR_HEADER_SIZE = 28,
    R6_TIR_FILE_SIZE = 32,
    R6_TIR_SPAN_SIZE = 8,
    R6_TIR_FILES = 240,
    R6_TIR_SPANS = 3840,
    R6_TIR_SOURCE = 165906,
    R6_TIR_MAX_STRING = 96
};

static const unsigned char tir_magic[8] = {
    'R', '6', 'T', 'I', 'R', 0, 1, 0
};

static const char *const tire_prefix = "TIRE_";
static const char *const scale_prefix = "WHEEL_SCALE_";
static const char *const width_prefix = "TIRE_WIDTH_SCALE_";

static int tir_header(const void *data, size_t size,
                      r6_tire_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tire_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_TIR_HEADER_SIZE ||
            r6_memcmp(bytes, tir_magic, sizeof(tir_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_TIR_FILES ||
            r6_u32(bytes, 16) != R6_TIR_SPANS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_TIR_SOURCE) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.span_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    base = R6_TIR_HEADER_SIZE +
           (size_t)header.file_count * R6_TIR_FILE_SIZE +
           (size_t)header.span_count * R6_TIR_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t tir_spans_base(void) {
    return R6_TIR_HEADER_SIZE + R6_TIR_FILES * R6_TIR_FILE_SIZE;
}

static size_t tir_strings_base(void) {
    return tir_spans_base() + R6_TIR_SPANS * R6_TIR_SPAN_SIZE;
}

static int tir_string(const void *data,
                      const r6_tire_header_t *header,
                      uint32_t offset, uint32_t length, int allow_empty) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = tir_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_TIR_MAX_STRING || (size_t)offset < base ||
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

static int tir_copy(const void *data,
                    const r6_tire_header_t *header,
                    uint32_t offset, uint32_t length,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result;
    if (!out || !capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    if (!length) {
        out[0] = 0;
        return R6_OK;
    }
    result = tir_string(data, header, offset, length, 0);
    if (result != R6_OK) {
        return result;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int tir_prefixed(const void *data,
                        const r6_tire_header_t *header,
                        const r6_tire_span_t *span,
                        const char *prefix, int require) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t length = r6_strlen(prefix);
    if (!span->length) {
        return require ? R6_ERR_FORMAT : R6_OK;
    }
    if (tir_string(data, header, span->offset, span->length, 0) != R6_OK ||
            span->length < length ||
            r6_memcmp(bytes + span->offset, prefix, length) != 0) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int tir_file(const void *data, size_t size, uint32_t index,
                    r6_tire_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tire_header_t header;
    r6_tire_file_t file;
    int result = tir_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&file, bytes + R6_TIR_HEADER_SIZE +
              (size_t)index * R6_TIR_FILE_SIZE, sizeof(file));
    if (!file.size || (file.lines != 30u && file.lines != 31u) ||
            file.span_base != index * 16u || file.color > 4u ||
            file.path_length < 8 ||
            tir_string(data, &header, file.path_offset,
                       file.path_length, 0) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".lua", 4) != 0 ||
            tir_string(data, &header, file.default_offset,
                       file.default_length, 0) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int tir_span(const void *data,
                    const r6_tire_header_t *header,
                    uint32_t index, r6_tire_span_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tire_span_t span;
    uint32_t file_index;
    int result;
    if (index >= header->span_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&span, bytes + tir_spans_base() +
              (size_t)index * R6_TIR_SPAN_SIZE, sizeof(span));
    if (span.length) {
        result = tir_string(data, header, span.offset, span.length, 0);
        if (result != R6_OK) {
            return result;
        }
    }
    file_index = index / 16u;
    if (file_index >= R6_TIR_FILES) {
        return R6_ERR_FORMAT;
    }
    switch (index % 16u) {
        case 0: case 1: case 2: case 3:
        case 4: case 5: case 6: case 7:
            result = tir_prefixed(data, header, &span, tire_prefix, 1);
            break;
        case 8: case 9: case 10: case 11:
            result = tir_prefixed(data, header, &span, scale_prefix, 0);
            break;
        default:
            result = tir_prefixed(data, header, &span, width_prefix, 0);
            break;
    }
    if (result != R6_OK) {
        return result;
    }
    r6_memcpy(out, &span, sizeof(span));
    return R6_OK;
}

int r6_tire_parse(const void *data, size_t size, r6_tire_header_t *out) {
    r6_tire_header_t header;
    r6_tire_file_t file;
    r6_tire_span_t span;
    uint32_t source = 0;
    uint32_t at;
    int result = tir_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = tir_file(data, size, at, &file);
        if (result != R6_OK) {
            return result;
        }
        source += file.size;
    }
    if (source != header.source_bytes) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.span_count; at++) {
        result = tir_span(data, &header, at, &span);
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_tire_file(const void *data, size_t size, uint32_t index,
                 r6_tire_file_t *out) {
    return tir_file(data, size, index, out);
}

int r6_tire_path(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tire_header_t header;
    r6_tire_file_t file;
    int result = tir_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tir_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return tir_copy(data, &header, file.path_offset, file.path_length,
                    out, capacity);
}

int r6_tire_span(const void *data, size_t size, uint32_t index,
                 r6_tire_span_t *out) {
    r6_tire_header_t header;
    int result = tir_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return tir_span(data, &header, index, out);
}

int r6_tire_text(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tire_header_t header;
    r6_tire_span_t span;
    int result = tir_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tir_span(data, &header, index, &span);
    if (result != R6_OK) {
        return result;
    }
    return tir_copy(data, &header, span.offset, span.length,
                    out, capacity);
}

int r6_tire_default(const void *data, size_t size, uint32_t index,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_tire_header_t header;
    r6_tire_file_t file;
    int result = tir_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = tir_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return tir_copy(data, &header, file.default_offset,
                    file.default_length, out, capacity);
}
