/* Bounds-checked reader for packed XMLT structural facts. Only copied names,
 * counts and indices cross the bridge; text values are never read. */

#include "r6/r6_xmlt_lists.h"

#include "core/internal.h"

enum {
    R6_XMLT_HEADER_SIZE = 44,
    R6_XMLT_FILE_SIZE = 16,
    R6_XMLT_LIST_SIZE = 20,
    R6_XMLT_SEED_SIZE = 12,
    R6_XMLT_FIELD_SIZE = 8
};

static const unsigned char xmlt_magic[8] = {
    'R', '6', 'X', 'L', 'T', 0, 1, 0
};

static size_t xmlt_file_offset(uint32_t index) {
    return R6_XMLT_HEADER_SIZE + (size_t)index * R6_XMLT_FILE_SIZE;
}

static size_t xmlt_list_offset(const r6_xmlt_header_t *header,
                               uint32_t index) {
    return R6_XMLT_HEADER_SIZE +
           (size_t)header->file_count * R6_XMLT_FILE_SIZE +
           (size_t)index * R6_XMLT_LIST_SIZE;
}

static size_t xmlt_seed_offset(const r6_xmlt_header_t *header,
                               uint32_t index) {
    return xmlt_list_offset(header, header->list_count) +
           (size_t)index * R6_XMLT_SEED_SIZE;
}

static size_t xmlt_field_offset(const r6_xmlt_header_t *header,
                                uint32_t index) {
    return xmlt_seed_offset(header, header->seed_count) +
           (size_t)index * R6_XMLT_FIELD_SIZE;
}

static size_t xmlt_string_base(const r6_xmlt_header_t *header) {
    return xmlt_field_offset(header, header->field_count);
}

static int xmlt_string_at(const void *data, size_t size,
                          const r6_xmlt_header_t *header, uint32_t skip,
                          char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t at = xmlt_string_base(header);
    size_t end = at + header->string_size;
    uint32_t index;
    if (!out) {
        return R6_ERR_ARG;
    }
    for (index = 0; index < skip; index++) {
        while (at < end && bytes[at]) {
            at++;
        }
        if (at == end) {
            return R6_ERR_FORMAT;
        }
        at++;
    }
    if (at == end) {
        return R6_ERR_FORMAT;
    }
    index = 0;
    while (at + index < end && bytes[at + index]) {
        if (bytes[at + index] >= 0x80u ||
                (size_t)(index + 1) >= capacity) {
            return R6_ERR_BUFFER;
        }
        index++;
    }
    if (at + index == end) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + at, index);
    out[index] = 0;
    return R6_OK;
}

static void xmlt_read_file(const void *data, uint32_t index,
                           r6_xmlt_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t row = xmlt_file_offset(index);
    out->list_first = r6_u32(bytes, row + 8);
    out->list_count = r6_u32(bytes, row + 12);
}

static void xmlt_read_list(const void *data, const r6_xmlt_header_t *header,
                           uint32_t index, r6_xmlt_list_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t row = xmlt_list_offset(header, index);
    out->type_index = r6_u32(bytes, row);
    out->seed_first = r6_u32(bytes, row + 4);
    out->seed_count = r6_u32(bytes, row + 8);
    out->field_first = r6_u32(bytes, row + 12);
    out->field_count = r6_u32(bytes, row + 16);
}

static void xmlt_read_seed(const void *data, const r6_xmlt_header_t *header,
                           uint32_t index, r6_xmlt_seed_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t row = xmlt_seed_offset(header, index);
    out->list_index = r6_u32(bytes, row);
    out->field_first = r6_u32(bytes, row + 4);
    out->field_count = r6_u32(bytes, row + 8);
}

static void xmlt_read_field(const void *data, const r6_xmlt_header_t *header,
                            uint32_t index, r6_xmlt_field_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t row = xmlt_field_offset(header, index);
    out->seed_index = r6_u32(bytes, row);
    out->tag_index = r6_u32(bytes, row + 4);
}

static int xmlt_layout(const void *data, size_t size,
                       r6_xmlt_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_xmlt_header_t header;
    size_t files;
    size_t lists;
    size_t seeds;
    size_t fields;
    size_t expected;
    uint32_t at;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_XMLT_HEADER_SIZE ||
            r6_memcmp(bytes, xmlt_magic, sizeof(xmlt_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.list_count = r6_u32(bytes, 16);
    header.seed_count = r6_u32(bytes, 20);
    header.field_count = r6_u32(bytes, 24);
    header.type_count = r6_u32(bytes, 28);
    header.tag_count = r6_u32(bytes, 32);
    header.string_size = r6_u32(bytes, 36);
    header.reserved = r6_u32(bytes, 40);
    if (!header.file_count || !header.list_count || !header.seed_count ||
            !header.field_count || !header.type_count || !header.tag_count ||
            !header.string_size || header.reserved ||
            header.file_count > ((size_t)-1 - R6_XMLT_HEADER_SIZE) /
                                R6_XMLT_FILE_SIZE ||
            header.list_count > ((size_t)-1 - R6_XMLT_HEADER_SIZE -
                                 (size_t)header.file_count *
                                 R6_XMLT_FILE_SIZE) / R6_XMLT_LIST_SIZE ||
            header.seed_count > ((size_t)-1 - R6_XMLT_HEADER_SIZE -
                                 (size_t)header.file_count *
                                 R6_XMLT_FILE_SIZE -
                                 (size_t)header.list_count *
                                 R6_XMLT_LIST_SIZE) / R6_XMLT_SEED_SIZE ||
            header.field_count > ((size_t)-1 - R6_XMLT_HEADER_SIZE -
                                  (size_t)header.file_count *
                                  R6_XMLT_FILE_SIZE -
                                  (size_t)header.list_count *
                                  R6_XMLT_LIST_SIZE -
                                  (size_t)header.seed_count *
                                  R6_XMLT_SEED_SIZE) / R6_XMLT_FIELD_SIZE) {
        return R6_ERR_FORMAT;
    }
    files = (size_t)header.file_count * R6_XMLT_FILE_SIZE;
    lists = (size_t)header.list_count * R6_XMLT_LIST_SIZE;
    seeds = (size_t)header.seed_count * R6_XMLT_SEED_SIZE;
    fields = (size_t)header.field_count * R6_XMLT_FIELD_SIZE;
    expected = R6_XMLT_HEADER_SIZE + files + lists + seeds + fields +
               header.string_size;
    if (expected < R6_XMLT_HEADER_SIZE + files + lists ||
            expected < R6_XMLT_HEADER_SIZE + files + lists + seeds ||
            expected < R6_XMLT_HEADER_SIZE + files + lists + seeds + fields ||
            expected != size) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.file_count; at++) {
        r6_xmlt_file_t file;
        uint32_t offset;
        uint32_t length;
        size_t row = xmlt_file_offset(at);
        size_t base = xmlt_string_base(&header);
        size_t end = base + header.string_size;
        size_t cursor;
        xmlt_read_file(data, at, &file);
        offset = r6_u32(bytes, row);
        length = r6_u32(bytes, row + 4);
        if (!length || offset < base || offset >= end ||
                (size_t)offset + length >= end ||
                file.list_first > header.list_count ||
                file.list_count > header.list_count - file.list_first) {
            return R6_ERR_FORMAT;
        }
        cursor = offset;
        while (cursor < end && bytes[cursor]) {
            cursor++;
        }
        if (cursor != (size_t)offset + length) {
            return R6_ERR_FORMAT;
        }
        if (at + 1u < header.file_count) {
            r6_xmlt_file_t next;
            xmlt_read_file(data, at + 1u, &next);
            if (file.list_first > next.list_first ||
                    next.list_first - file.list_first != file.list_count) {
                return R6_ERR_FORMAT;
            }
        } else if (file.list_first != header.list_count - file.list_count) {
            return R6_ERR_FORMAT;
        }
    }
    for (at = 0; at < header.list_count; at++) {
        r6_xmlt_list_t list;
        xmlt_read_list(data, &header, at, &list);
        if (list.type_index >= header.type_count ||
                list.seed_first > header.seed_count ||
                list.seed_count > header.seed_count - list.seed_first ||
                list.field_first > header.field_count ||
                list.field_count > header.field_count - list.field_first) {
            return R6_ERR_FORMAT;
        }
        if (list.seed_count) {
            r6_xmlt_seed_t first_seed;
            r6_xmlt_seed_t last_seed;
            xmlt_read_seed(data, &header, list.seed_first, &first_seed);
            xmlt_read_seed(data, &header,
                           list.seed_first + list.seed_count - 1u,
                           &last_seed);
            if (first_seed.field_first != list.field_first ||
                    last_seed.field_first > header.field_count ||
                    last_seed.field_count > header.field_count -
                    last_seed.field_first ||
                    last_seed.field_first + last_seed.field_count !=
                    list.field_first + list.field_count) {
                return R6_ERR_FORMAT;
            }
        } else if (list.field_count) {
            return R6_ERR_FORMAT;
        }
        if (at + 1u < header.list_count) {
            r6_xmlt_list_t next;
            xmlt_read_list(data, &header, at + 1u, &next);
            if (list.seed_first > next.seed_first ||
                    next.seed_first - list.seed_first != list.seed_count ||
                    list.field_first > next.field_first ||
                    next.field_first - list.field_first != list.field_count) {
                return R6_ERR_FORMAT;
            }
        } else if (list.seed_first != header.seed_count - list.seed_count ||
                   list.field_first != header.field_count - list.field_count) {
            return R6_ERR_FORMAT;
        }
    }
    for (at = 0; at < header.seed_count; at++) {
        r6_xmlt_seed_t seed;
        xmlt_read_seed(data, &header, at, &seed);
        if (!seed.field_count || seed.list_index >= header.list_count ||
                seed.field_first > header.field_count ||
                seed.field_count > header.field_count - seed.field_first) {
            return R6_ERR_FORMAT;
        }
        if (at + 1u < header.seed_count) {
            r6_xmlt_seed_t next;
            xmlt_read_seed(data, &header, at + 1u, &next);
            if (seed.field_first > next.field_first ||
                    next.field_first - seed.field_first != seed.field_count) {
                return R6_ERR_FORMAT;
            }
        } else if (seed.field_first != header.field_count - seed.field_count) {
            return R6_ERR_FORMAT;
        }
    }
    for (at = 0; at < header.field_count; at++) {
        r6_xmlt_field_t field;
        r6_xmlt_seed_t seed;
        xmlt_read_field(data, &header, at, &field);
        if (field.seed_index >= header.seed_count ||
                field.tag_index >= header.tag_count) {
            return R6_ERR_FORMAT;
        }
        xmlt_read_seed(data, &header, field.seed_index, &seed);
        if (at < seed.field_first ||
                at - seed.field_first >= seed.field_count) {
            return R6_ERR_FORMAT;
        }
    }
    for (at = 0; at < header.type_count; at++) {
        char name[64];
        if (xmlt_string_at(data, size, &header, header.file_count + at,
                           name, sizeof(name)) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    for (at = 0; at < header.tag_count; at++) {
        char name[64];
        if (xmlt_string_at(data, size, &header,
                           header.file_count + header.type_count + at,
                           name, sizeof(name)) != R6_OK) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_xmlt_lists_parse(const void *data, size_t size,
                        r6_xmlt_header_t *out) {
    return xmlt_layout(data, size, out);
}

int r6_xmlt_file(const void *data, size_t size, uint32_t index,
                 r6_xmlt_file_t *out) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    xmlt_read_file(data, index, out);
    return R6_OK;
}

int r6_xmlt_path(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    return xmlt_string_at(data, size, &header, index, out, capacity);
}

int r6_xmlt_list(const void *data, size_t size, uint32_t index,
                 r6_xmlt_list_t *out) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.list_count || !out) {
        return R6_ERR_ARG;
    }
    xmlt_read_list(data, &header, index, out);
    return R6_OK;
}

int r6_xmlt_type(const void *data, size_t size, uint32_t index,
                 char *out, size_t capacity) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.type_count) {
        return R6_ERR_ARG;
    }
    return xmlt_string_at(data, size, &header, header.file_count + index,
                          out, capacity);
}

int r6_xmlt_seed(const void *data, size_t size, uint32_t index,
                 r6_xmlt_seed_t *out) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.seed_count || !out) {
        return R6_ERR_ARG;
    }
    xmlt_read_seed(data, &header, index, out);
    return R6_OK;
}

int r6_xmlt_field(const void *data, size_t size, uint32_t index,
                  r6_xmlt_field_t *out) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.field_count || !out) {
        return R6_ERR_ARG;
    }
    xmlt_read_field(data, &header, index, out);
    return R6_OK;
}

int r6_xmlt_tag(const void *data, size_t size, uint32_t index,
                char *out, size_t capacity) {
    r6_xmlt_header_t header;
    int result = xmlt_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.tag_count) {
        return R6_ERR_ARG;
    }
    return xmlt_string_at(data, size, &header,
                          header.file_count + header.type_count + index,
                          out, capacity);
}
