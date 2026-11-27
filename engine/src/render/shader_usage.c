/* Bounded reader for the derived R6SCU shader usage map. */

#include "r6/r6_shader_usage.h"

#include "core/internal.h"

static const unsigned char shader_usage_magic[8] = {
    'R', '6', 'S', 'C', 'U', 0, 1, 0
};

static int usage_header(const void *data, size_t size,
                        r6_shader_usage_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint64_t uniform_end;
    uint64_t resource_end;
    uint64_t declared_end;
    uint64_t strings_end;
    if (!bytes || !out || size < 52u ||
        r6_memcmp(bytes, shader_usage_magic,
                  sizeof(shader_usage_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) == 0u ||
        r6_u32(bytes, 16) == 0u || r6_u32(bytes, 20) == 0u ||
        r6_u32(bytes, 28) != 52u) {
        return R6_ERR_FORMAT;
    }
    uniform_end = (uint64_t)r6_u32(bytes, 28) +
                  (uint64_t)r6_u32(bytes, 12) * 44u;
    resource_end = uniform_end + (uint64_t)r6_u32(bytes, 16) * 8u;
    declared_end = resource_end + (uint64_t)r6_u32(bytes, 20) * 8u;
    strings_end = declared_end + (uint64_t)r6_u32(bytes, 24) * 4u;
    if (r6_u32(bytes, 32) != uniform_end ||
        r6_u32(bytes, 36) != resource_end ||
        r6_u32(bytes, 40) != declared_end ||
        r6_u32(bytes, 44) != strings_end ||
        !r6_u32(bytes, 48) || strings_end + r6_u32(bytes, 48) != size) {
        return R6_ERR_FORMAT;
    }
    out->version = 1u;
    out->record_count = r6_u32(bytes, 12);
    out->uniform_count = r6_u32(bytes, 16);
    out->resource_count = r6_u32(bytes, 20);
    out->declared_count = r6_u32(bytes, 24);
    out->record_off = 52u;
    out->uniform_off = (uint32_t)uniform_end;
    out->resource_off = (uint32_t)resource_end;
    out->declared_off = (uint32_t)declared_end;
    out->strings_off = (uint32_t)strings_end;
    out->strings_size = r6_u32(bytes, 48);
    return R6_OK;
}

static int usage_string(const unsigned char *bytes,
                        const r6_shader_usage_header *h, uint32_t offset,
                        char *name, size_t capacity) {
    uint32_t end = h->strings_off + h->strings_size;
    uint32_t at = offset;
    size_t written = 0;
    if (!name || !capacity || offset < h->strings_off || offset >= end) {
        return R6_ERR_ARG;
    }
    while (at < end && bytes[at]) {
        if (written + 1u >= capacity) {
            return R6_ERR_BUFFER;
        }
        name[written++] = (char)bytes[at++];
    }
    if (at >= end) {
        return R6_ERR_FORMAT;
    }
    name[written] = 0;
    return R6_OK;
}

int r6_shader_usage_parse(const void *data, size_t size,
                          r6_shader_usage_header *out) {
    return usage_header(data, size, out);
}

int r6_shader_usage_record(const void *data, size_t size, uint32_t index,
                           r6_shader_usage_record_t *out) {
    r6_shader_usage_header h;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    int result = usage_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!out || index >= h.record_count ||
        h.record_off + (uint64_t)index * 44u + 44u > h.uniform_off) {
        return R6_ERR_ARG;
    }
    offset = h.record_off + index * 44u;
    out->name_off = r6_u32(bytes, offset);
    out->stage = r6_u32(bytes, offset + 4u);
    out->uniform_first = r6_u32(bytes, offset + 8u);
    out->uniform_count = r6_u32(bytes, offset + 12u);
    out->dynamic_cbuffer = r6_u32(bytes, offset + 16u);
    out->resource_first = r6_u32(bytes, offset + 20u);
    out->resource_count = r6_u32(bytes, offset + 24u);
    out->declared_first = r6_u32(bytes, offset + 28u);
    out->declared_count = r6_u32(bytes, offset + 32u);
    out->dynamic_resource = r6_u32(bytes, offset + 36u);
    out->unmapped_resource = r6_u32(bytes, offset + 40u);
    if (out->stage > R6_SHADER_USAGE_STAGE_PIXEL ||
        out->name_off < h.strings_off ||
        out->name_off >= h.strings_off + h.strings_size ||
        (uint64_t)out->uniform_first + out->uniform_count > h.uniform_count ||
        (uint64_t)out->resource_first + out->resource_count >
        h.resource_count ||
        (uint64_t)out->declared_first + out->declared_count >
        h.declared_count) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_shader_usage_name(const void *data, size_t size, uint32_t index,
                         char *name, size_t capacity) {
    r6_shader_usage_header h;
    r6_shader_usage_record_t row;
    const unsigned char *bytes = (const unsigned char *)data;
    int result = r6_shader_usage_record(data, size, index, &row);
    if (result != R6_OK) {
        return result;
    }
    result = usage_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    return usage_string(bytes, &h, row.name_off, name, capacity);
}

int r6_shader_usage_find(const void *data, size_t size, const char *name,
                         uint32_t stage, uint32_t *index) {
    r6_shader_usage_header h;
    r6_shader_usage_record_t row;
    uint32_t at;
    char candidate[R6_SHADER_USAGE_NAME_CAP];
    size_t wanted;
    int result = usage_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !index || stage > R6_SHADER_USAGE_STAGE_PIXEL) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < h.record_count; at++) {
        result = r6_shader_usage_record(data, size, at, &row);
        if (result != R6_OK) {
            return result;
        }
        if (row.stage != stage) {
            continue;
        }
        result = r6_shader_usage_name(data, size, at, candidate,
                                      sizeof(candidate));
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(candidate) == wanted &&
            r6_memcmp(candidate, name, wanted) == 0) {
            *index = at;
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

static int usage_named(const void *data, size_t size, uint32_t record,
                       uint32_t index, uint32_t kind, char *name,
                       size_t capacity, uint32_t *count) {
    r6_shader_usage_header h;
    r6_shader_usage_record_t row;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t first;
    uint32_t total;
    uint32_t offset;
    uint32_t name_off;
    int result = usage_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    result = r6_shader_usage_record(data, size, record, &row);
    if (result != R6_OK) {
        return result;
    }
    if (kind == 0u) {
        first = row.uniform_first;
        total = row.uniform_count;
        offset = h.uniform_off;
    } else {
        first = row.resource_first;
        total = row.resource_count;
        offset = h.resource_off;
    }
    if (index >= total || !name || !capacity) {
        return R6_ERR_ARG;
    }
    offset += (first + index) * 8u;
    name_off = r6_u32(bytes, offset);
    if (count) {
        *count = r6_u32(bytes, offset + 4u);
    }
    return usage_string(bytes, &h, name_off, name, capacity);
}

int r6_shader_usage_uniform(const void *data, size_t size, uint32_t record,
                            uint32_t index, char *name, size_t capacity,
                            uint32_t *count) {
    return usage_named(data, size, record, index, 0u, name, capacity, count);
}

int r6_shader_usage_resource(const void *data, size_t size, uint32_t record,
                             uint32_t index, char *name, size_t capacity,
                             uint32_t *count) {
    return usage_named(data, size, record, index, 1u, name, capacity, count);
}

static int usage_find_named(const void *data, size_t size, uint32_t record,
                            uint32_t kind, const char *name, uint32_t *index,
                            uint32_t *count) {
    r6_shader_usage_record_t row;
    uint32_t at;
    char candidate[R6_SHADER_USAGE_NAME_CAP];
    uint32_t found_count = 0;
    size_t wanted;
    int result = r6_shader_usage_record(data, size, record, &row);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !index) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < (kind == 0u ? row.uniform_count : row.resource_count);
         at++) {
        result = kind == 0u ?
                 r6_shader_usage_uniform(data, size, record, at, candidate,
                                         sizeof(candidate), &found_count) :
                 r6_shader_usage_resource(data, size, record, at, candidate,
                                          sizeof(candidate), &found_count);
        if (result != R6_OK) {
            return result;
        }
        if (r6_strlen(candidate) == wanted &&
            r6_memcmp(candidate, name, wanted) == 0) {
            *index = at;
            if (count) {
                *count = found_count;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_shader_usage_find_uniform(const void *data, size_t size,
                                 uint32_t record, const char *name,
                                 uint32_t *index, uint32_t *count) {
    return usage_find_named(data, size, record, 0u, name, index, count);
}

int r6_shader_usage_find_resource(const void *data, size_t size,
                                  uint32_t record, const char *name,
                                  uint32_t *index, uint32_t *count) {
    return usage_find_named(data, size, record, 1u, name, index, count);
}

int r6_shader_usage_declared(const void *data, size_t size, uint32_t record,
                             uint32_t index, char *name, size_t capacity) {
    r6_shader_usage_header h;
    r6_shader_usage_record_t row;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    int result = usage_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    result = r6_shader_usage_record(data, size, record, &row);
    if (result != R6_OK) {
        return result;
    }
    if (index >= row.declared_count || !name || !capacity) {
        return R6_ERR_ARG;
    }
    offset = h.declared_off + (row.declared_first + index) * 4u;
    return usage_string(bytes, &h, r6_u32(bytes, offset), name, capacity);
}
