/* Bounds-checked reader for packed root INI facts. */

#include "r6/r6_root_ini_catalog.h"

#include "core/internal.h"

enum {
    R6_RI_HEADER_SIZE = 32,
    R6_RI_FILE_SIZE = 40,
    R6_RI_KEY_SIZE = 16,
    R6_RI_SPAN_SIZE = 8,
    R6_RI_FILES = 2,
    R6_RI_KEYS = 41,
    R6_RI_COMMENTS = 3,
    R6_RI_SOURCE = 1039,
    R6_RI_MAX_STRING = 128
};

static const unsigned char ri_magic[8] = {
    'R', '6', 'I', 'N', 'I', 0, 1, 0
};

static int ri_header(const void *data, size_t size,
                     r6_root_ini_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_RI_HEADER_SIZE ||
            r6_memcmp(bytes, ri_magic, sizeof(ri_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) != R6_RI_FILES ||
            r6_u32(bytes, 16) != R6_RI_KEYS || !r6_u32(bytes, 20) ||
            r6_u32(bytes, 24) != R6_RI_SOURCE ||
            r6_u32(bytes, 28) != R6_RI_COMMENTS) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.file_count = r6_u32(bytes, 12);
    header.key_count = r6_u32(bytes, 16);
    header.string_size = r6_u32(bytes, 20);
    header.source_bytes = r6_u32(bytes, 24);
    header.comment_count = r6_u32(bytes, 28);
    base = R6_RI_HEADER_SIZE +
           (size_t)header.file_count * R6_RI_FILE_SIZE +
           (size_t)header.key_count * R6_RI_KEY_SIZE +
           (size_t)header.comment_count * R6_RI_SPAN_SIZE +
           header.string_size;
    if (base != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t ri_keys_base(void) {
    return R6_RI_HEADER_SIZE + R6_RI_FILES * R6_RI_FILE_SIZE;
}

static size_t ri_comments_base(void) {
    return ri_keys_base() + R6_RI_KEYS * R6_RI_KEY_SIZE;
}

static size_t ri_strings_base(void) {
    return ri_comments_base() + R6_RI_COMMENTS * R6_RI_SPAN_SIZE;
}

static int ri_string(const void *data,
                     const r6_root_ini_header_t *header,
                     uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = ri_strings_base();
    size_t end = base + header->string_size;
    size_t at;
    if (length > R6_RI_MAX_STRING || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u ||
            bytes[(size_t)offset + length] != 0) {
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

static int ri_copy(const void *data,
                   const r6_root_ini_header_t *header,
                   uint32_t offset, uint32_t length,
                   char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    int result = ri_string(data, header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out || (size_t)length + 1u > capacity) {
        return out ? R6_ERR_BUFFER : R6_ERR_ARG;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

static int ri_file(const void *data, size_t size, uint32_t index,
                   r6_root_ini_file_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_header_t header;
    r6_root_ini_file_t file;
    size_t at;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_RI_HEADER_SIZE + (size_t)index * R6_RI_FILE_SIZE;
    r6_memcpy(&file, bytes + at, sizeof(file));
    if (!file.size || !file.lines || !file.keys ||
            file.key_base > header.key_count ||
            file.keys > header.key_count - file.key_base ||
            file.comment_base > header.comment_count ||
            file.comments > header.comment_count - file.comment_base ||
            file.path_length < 4 ||
            ri_string(data, &header, file.path_offset,
                      file.path_length) != R6_OK ||
            r6_memcmp(bytes + file.path_offset + file.path_length - 4,
                      ".ini", 4) != 0 || file.section_length < 3 ||
            ri_string(data, &header, file.section_offset,
                      file.section_length) != R6_OK ||
            bytes[file.section_offset] != '[' ||
            bytes[file.section_offset + file.section_length - 1u] != ']') {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &file, sizeof(file));
    return R6_OK;
}

static int ri_key(const void *data,
                  const r6_root_ini_header_t *header,
                  uint32_t index, r6_root_ini_key_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_key_t key;
    size_t at = ri_keys_base() + (size_t)index * R6_RI_KEY_SIZE;
    if (index >= header->key_count || !out) {
        return R6_ERR_ARG;
    }
    r6_memcpy(&key, bytes + at, sizeof(key));
    if (!key.key_length ||
            ri_string(data, header, key.key_offset, key.key_length) != R6_OK ||
            ri_string(data, header, key.value_offset,
                      key.value_length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &key, sizeof(key));
    return R6_OK;
}

static int ri_comment(const void *data,
                      const r6_root_ini_header_t *header,
                      uint32_t index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    uint32_t length;
    size_t at = ri_comments_base() + (size_t)index * R6_RI_SPAN_SIZE;
    if (index >= header->comment_count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    if (length < 2 || bytes[offset] != ';' ||
            ri_string(data, header, offset, length) != R6_OK) {
        return R6_ERR_FORMAT;
    }
    return ri_copy(data, header, offset, length, out, capacity);
}

int r6_root_ini_parse(const void *data, size_t size,
                      r6_root_ini_header_t *out) {
    r6_root_ini_header_t header;
    r6_root_ini_file_t file;
    r6_root_ini_key_t key;
    char text[R6_RI_MAX_STRING + 1];
    uint32_t keys = 0;
    uint32_t comments = 0;
    uint32_t source = 0;
    uint32_t at;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.file_count; at++) {
        result = ri_file(data, size, at, &file);
        if (result != R6_OK || file.key_base != keys ||
                file.comment_base != comments) {
            return R6_ERR_FORMAT;
        }
        source += file.size;
        keys += file.keys;
        comments += file.comments;
    }
    if (source != header.source_bytes || keys != header.key_count ||
            comments != header.comment_count) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < header.key_count; at++) {
        result = ri_key(data, &header, at, &key);
        if (result != R6_OK) {
            return result;
        }
    }
    for (at = 0; at < header.comment_count; at++) {
        result = ri_comment(data, &header, at, text, sizeof(text));
        if (result != R6_OK) {
            return result;
        }
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_root_ini_file(const void *data, size_t size, uint32_t index,
                     r6_root_ini_file_t *out) {
    return ri_file(data, size, index, out);
}

int r6_root_ini_path(const void *data, size_t size, uint32_t index,
                     char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_header_t header;
    r6_root_ini_file_t file;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ri_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return ri_copy(data, &header, file.path_offset, file.path_length,
                   out, capacity);
}

int r6_root_ini_section(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_header_t header;
    r6_root_ini_file_t file;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ri_file(data, size, index, &file);
    if (result != R6_OK) {
        return result;
    }
    return ri_copy(data, &header, file.section_offset, file.section_length,
                   out, capacity);
}

int r6_root_ini_key(const void *data, size_t size, uint32_t index,
                    char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_header_t header;
    r6_root_ini_key_t key;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ri_key(data, &header, index, &key);
    if (result != R6_OK) {
        return result;
    }
    return ri_copy(data, &header, key.key_offset, key.key_length,
                   out, capacity);
}

int r6_root_ini_value(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_root_ini_header_t header;
    r6_root_ini_key_t key;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    result = ri_key(data, &header, index, &key);
    if (result != R6_OK) {
        return result;
    }
    return ri_copy(data, &header, key.value_offset, key.value_length,
                   out, capacity);
}

int r6_root_ini_comment(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    r6_root_ini_header_t header;
    int result = ri_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    return ri_comment(data, &header, index, out, capacity);
}
