/* Bounded reader for the derived R6SCF control-flow map. */

#include "r6/r6_shader_cf.h"

#include "core/internal.h"

static const unsigned char shader_cf_magic[8] = {
    'R', '6', 'S', 'C', 'F', 0, 1, 0
};

static int cf_header(const void *data, size_t size,
                     r6_shader_cf_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint64_t blocks_end;
    uint64_t cases_end;
    uint64_t indices_end;
    uint64_t strings_end;
    if (!bytes || !out || size < 52u ||
        r6_memcmp(bytes, shader_cf_magic,
                  sizeof(shader_cf_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u || r6_u32(bytes, 12) == 0u ||
        r6_u32(bytes, 16) == 0u || r6_u32(bytes, 24) == 0u ||
        r6_u32(bytes, 28) != 52u) {
        return R6_ERR_FORMAT;
    }
    blocks_end = (uint64_t)r6_u32(bytes, 28) +
                 (uint64_t)r6_u32(bytes, 12) * 24u;
    cases_end = blocks_end + (uint64_t)r6_u32(bytes, 16) * 40u;
    indices_end = cases_end + (uint64_t)r6_u32(bytes, 20) * 8u;
    strings_end = indices_end + (uint64_t)r6_u32(bytes, 24) * 4u;
    if (r6_u32(bytes, 32) != blocks_end ||
        r6_u32(bytes, 36) != cases_end ||
        r6_u32(bytes, 40) != indices_end ||
        r6_u32(bytes, 44) != strings_end ||
        !r6_u32(bytes, 48) || strings_end + r6_u32(bytes, 48) != size) {
        return R6_ERR_FORMAT;
    }
    out->version = 1u;
    out->record_count = r6_u32(bytes, 12);
    out->block_count = r6_u32(bytes, 16);
    out->case_count = r6_u32(bytes, 20);
    out->index_count = r6_u32(bytes, 24);
    out->records_off = 52u;
    out->blocks_off = (uint32_t)blocks_end;
    out->cases_off = (uint32_t)cases_end;
    out->indices_off = (uint32_t)indices_end;
    out->strings_off = (uint32_t)strings_end;
    out->strings_size = r6_u32(bytes, 48);
    return R6_OK;
}

static int cf_string(const unsigned char *bytes, const r6_shader_cf_header *h,
                     uint32_t offset, char *name, size_t capacity) {
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

int r6_shader_cf_parse(const void *data, size_t size,
                       r6_shader_cf_header *out) {
    return cf_header(data, size, out);
}

int r6_shader_cf_record(const void *data, size_t size, uint32_t index,
                        r6_shader_cf_record_t *out) {
    r6_shader_cf_header h;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    int result = cf_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!out || index >= h.record_count ||
        h.records_off + (uint64_t)index * 24u + 24u > h.blocks_off) {
        return R6_ERR_ARG;
    }
    offset = h.records_off + index * 24u;
    out->name_off = r6_u32(bytes, offset);
    out->stage = r6_u32(bytes, offset + 4u);
    out->first_block = r6_u32(bytes, offset + 8u);
    out->block_count = r6_u32(bytes, offset + 12u);
    out->unmatched_first = r6_u32(bytes, offset + 16u);
    out->unmatched_count = r6_u32(bytes, offset + 20u);
    if (out->stage > R6_SHADER_CF_STAGE_PIXEL ||
        out->name_off < h.strings_off ||
        out->name_off >= h.strings_off + h.strings_size ||
        (uint64_t)out->first_block + out->block_count > h.block_count ||
        out->unmatched_first < h.indices_off / 4u ||
        (uint64_t)out->unmatched_first + out->unmatched_count >
        h.indices_off / 4u + h.index_count) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_shader_cf_name(const void *data, size_t size, uint32_t index,
                      char *name, size_t capacity) {
    r6_shader_cf_header h;
    r6_shader_cf_record_t row;
    const unsigned char *bytes = (const unsigned char *)data;
    int result = r6_shader_cf_record(data, size, index, &row);
    if (result != R6_OK) {
        return result;
    }
    result = cf_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    (void)bytes;
    return cf_string(bytes, &h, row.name_off, name, capacity);
}

int r6_shader_cf_find(const void *data, size_t size, const char *name,
                      uint32_t stage, uint32_t *index) {
    r6_shader_cf_header h;
    r6_shader_cf_record_t row;
    uint32_t at;
    char candidate[R6_SHADER_CF_NAME_CAP];
    size_t wanted;
    int result = cf_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !index || stage > R6_SHADER_CF_STAGE_PIXEL) {
        return R6_ERR_ARG;
    }
    wanted = r6_strlen(name);
    if (!wanted) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < h.record_count; at++) {
        result = r6_shader_cf_record(data, size, at, &row);
        if (result != R6_OK) {
            return result;
        }
        if (row.stage != stage) {
            continue;
        }
        result = r6_shader_cf_name(data, size, at, candidate,
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

int r6_shader_cf_block(const void *data, size_t size, uint32_t index,
                       r6_shader_cf_block_t *out) {
    r6_shader_cf_header h;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    int result = cf_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!out || index >= h.block_count ||
        h.blocks_off + (uint64_t)index * 40u + 40u > h.cases_off) {
        return R6_ERR_ARG;
    }
    offset = h.blocks_off + index * 40u;
    out->kind = r6_u32(bytes, offset);
    out->start = r6_u32(bytes, offset + 4u);
    out->end = r6_u32(bytes, offset + 8u);
    out->else_index = r6_u32(bytes, offset + 12u);
    out->case_first = r6_u32(bytes, offset + 16u);
    out->case_count = r6_u32(bytes, offset + 20u);
    out->break_first = r6_u32(bytes, offset + 24u);
    out->break_count = r6_u32(bytes, offset + 28u);
    out->continue_first = r6_u32(bytes, offset + 32u);
    out->continue_count = r6_u32(bytes, offset + 36u);
    if (out->kind > R6_SHADER_CF_SWITCH || out->start > out->end ||
        out->case_first < h.cases_off / 8u ||
        out->break_first < h.indices_off / 4u ||
        out->continue_first < h.indices_off / 4u ||
        (uint64_t)out->case_first + out->case_count >
        h.cases_off / 8u + h.case_count ||
        (uint64_t)out->break_first + out->break_count >
        h.indices_off / 4u + h.index_count ||
        (uint64_t)out->continue_first + out->continue_count >
        h.indices_off / 4u + h.index_count ||
        (out->else_index != R6_SHADER_CF_NO_ELSE &&
         (out->else_index < out->start || out->else_index > out->end))) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_shader_cf_case(const void *data, size_t size, uint32_t index,
                      r6_shader_cf_case_t *out) {
    r6_shader_cf_header h;
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t offset;
    int result = cf_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!out || index >= h.case_count ||
        h.cases_off + (uint64_t)index * 8u + 8u > h.indices_off) {
        return R6_ERR_ARG;
    }
    offset = h.cases_off + index * 8u;
    out->kind = r6_u32(bytes, offset);
    out->start = r6_u32(bytes, offset + 4u);
    return out->kind <= R6_SHADER_CF_DEFAULT ? R6_OK : R6_ERR_FORMAT;
}

int r6_shader_cf_index(const void *data, size_t size, uint32_t index,
                       uint32_t *out) {
    r6_shader_cf_header h;
    const unsigned char *bytes = (const unsigned char *)data;
    int result = cf_header(data, size, &h);
    if (result != R6_OK) {
        return result;
    }
    if (!out || index >= h.index_count ||
        h.indices_off + (uint64_t)index * 4u + 4u > h.strings_off) {
        return R6_ERR_ARG;
    }
    *out = r6_u32(bytes, h.indices_off + index * 4u);
    return R6_OK;
}
