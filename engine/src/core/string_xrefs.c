/* Bounded reader for the derived raw string-xref inventory. */

#include "r6/r6_string_xrefs.h"

#include "core/internal.h"

static const unsigned char string_xref_magic[8] = {
    'R', '6', 'S', 'X', 'R', 0, 1, 0
};

enum {
    R6_STRING_XREF_HEADER_SIZE = 48,
    R6_STRING_XREF_NAME_OFF = 48,
    R6_STRING_XREF_RVA_OFF = R6_STRING_XREF_NAME_OFF +
                             R6_STRING_XREF_NAMES * 12u,
    R6_STRING_XREF_STRINGS_OFF = R6_STRING_XREF_RVA_OFF +
                                 R6_STRING_XREF_RVAS * 4u
};

static int string_xref_header(const void *data, size_t size,
                              r6_string_xref_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_string_xref_header header;
    if (!bytes || !out || size < R6_STRING_XREF_HEADER_SIZE ||
        r6_memcmp(bytes, string_xref_magic,
                  sizeof(string_xref_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != 4885740u ||
        r6_u32(bytes, 16) != 51737u ||
        r6_u32(bytes, 20) != 336413u ||
        r6_u32(bytes, 24) != 219u ||
        r6_u32(bytes, 28) != 195u ||
        r6_u32(bytes, 32) != R6_STRING_XREF_NAMES ||
        r6_u32(bytes, 36) != R6_STRING_XREF_RVAS ||
        r6_u32(bytes, 44) != R6_STRING_XREF_STRINGS_OFF ||
        !r6_u32(bytes, 40) ||
        (size_t)R6_STRING_XREF_STRINGS_OFF + r6_u32(bytes, 40) != size) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.instructions = r6_u32(bytes, 12);
    header.string_refs = r6_u32(bytes, 16);
    header.strings = r6_u32(bytes, 20);
    header.names_requested = r6_u32(bytes, 24);
    header.names_found = r6_u32(bytes, 28);
    header.name_count = r6_u32(bytes, 32);
    header.rva_count = r6_u32(bytes, 36);
    header.strings_size = r6_u32(bytes, 40);
    header.strings_off = r6_u32(bytes, 44);
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int string_xref_name_text(const unsigned char *bytes, size_t size,
                                 uint32_t strings_off, uint32_t offset,
                                 char *out, size_t capacity) {
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < strings_off || offset >= size) {
        return R6_ERR_FORMAT;
    }
    while (at < size && bytes[at]) {
        at++;
    }
    if (at == size || at - offset >= capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, at - offset);
    out[at - offset] = 0;
    return R6_OK;
}

int r6_string_xref_parse(const void *data, size_t size,
                         r6_string_xref_header *out) {
    return string_xref_header(data, size, out);
}

int r6_string_xref_name(const void *data, size_t size, uint32_t index,
                        char *name, size_t capacity, uint32_t *rva_first,
                        uint32_t *rva_count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_string_xref_header header;
    uint32_t row_off;
    uint32_t first;
    uint32_t count;
    int result = string_xref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.name_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_STRING_XREF_NAME_OFF + index * 12u;
    first = r6_u32(bytes, row_off + 4u);
    count = r6_u32(bytes, row_off + 8u);
    if ((index == 0 && first != 0u) ||
        (index && first != r6_u32(bytes, row_off - 12u + 4u) +
                         r6_u32(bytes, row_off - 12u + 8u)) ||
        first + count > header.rva_count) {
        return R6_ERR_FORMAT;
    }
    if (name || capacity) {
        result = string_xref_name_text(bytes, size, header.strings_off,
                                       r6_u32(bytes, row_off), name,
                                       capacity);
        if (result != R6_OK) {
            return result;
        }
    }
    if (rva_first) {
        *rva_first = first;
    }
    if (rva_count) {
        *rva_count = count;
    }
    return R6_OK;
}

int r6_string_xref_rva(const void *data, size_t size, uint32_t index,
                       uint32_t *rva) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_string_xref_header header;
    uint32_t value;
    int result = string_xref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.rva_count) {
        return R6_ERR_ARG;
    }
    value = r6_u32(bytes, R6_STRING_XREF_RVA_OFF + index * 4u);
    if (value < 0x1000u || value >= 34308096u) {
        return R6_ERR_FORMAT;
    }
    if (rva) {
        *rva = value;
    }
    return R6_OK;
}

int r6_string_xref_name_rva(const void *data, size_t size,
                            uint32_t name_index, uint32_t local_index,
                            uint32_t *rva) {
    uint32_t first = 0;
    uint32_t count = 0;
    int result = r6_string_xref_name(data, size, name_index, NULL, 0, &first,
                                     &count);
    if (result == R6_ERR_ARG) {
        return R6_ERR_ARG;
    }
    if (result != R6_OK) {
        return result;
    }
    if (local_index >= count) {
        return R6_ERR_ARG;
    }
    return r6_string_xref_rva(data, size, first + local_index, rva);
}

int r6_string_xref_find(const void *data, size_t size, const char *name,
                        uint32_t *index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_string_xref_header header;
    size_t wanted;
    uint32_t at;
    int result = string_xref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!name) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.name_count; at++) {
        uint32_t offset = r6_u32(bytes, R6_STRING_XREF_NAME_OFF + at * 12u);
        uint32_t end = offset;
        while (end < size && bytes[end]) {
            end++;
        }
        if (end < size && end - offset == wanted &&
            r6_memcmp(bytes + offset, name, wanted) == 0) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_string_xref_find_rva(const void *data, size_t size, uint32_t rva,
                            uint32_t *indices, uint32_t capacity,
                            uint32_t *count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_string_xref_header header;
    uint32_t total = 0;
    uint32_t copied = 0;
    uint32_t index;
    int result = string_xref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (rva < 0x1000u || rva >= 34308096u || (capacity && !indices)) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < header.rva_count; index++) {
        if (r6_u32(bytes, R6_STRING_XREF_RVA_OFF + index * 4u) == rva) {
            if (copied < capacity) {
                indices[copied++] = index;
            }
            total++;
        }
    }
    if (count) {
        *count = total;
    }
    if (!total) {
        return R6_ERR_NOT_FOUND;
    }
    return total > capacity ? R6_ERR_BUFFER : R6_OK;
}
