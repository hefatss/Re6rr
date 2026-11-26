/* Bounded reader for the derived Enma input-simulation facts. Values stay as
 * copied bits; the core never interprets a float from host memory. */

#include "r6/r6_enma_sim.h"

#include "core/internal.h"

static const unsigned char enma_sim_magic[8] = {
    'R', '6', 'E', 'S', 'I', 'M', 0, 1
};

enum {
    R6_ENMA_SIM_HEADER_SIZE = 32,
    R6_ENMA_SIM_GETTER_OFF = 32,
    R6_ENMA_SIM_HIT_OFF = R6_ENMA_SIM_GETTER_OFF +
                          R6_ENMA_SIM_GETTERS * 24u,
    R6_ENMA_SIM_CONFIG_OFF = R6_ENMA_SIM_HIT_OFF + R6_ENMA_SIM_HITS * 8u
};

static int enma_header(const void *data, size_t size,
                       r6_enma_sim_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_sim_header header;
    if (!bytes || !out || size < R6_ENMA_SIM_HEADER_SIZE ||
        r6_memcmp(bytes, enma_sim_magic, sizeof(enma_sim_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_ENMA_SIM_GETTERS ||
        r6_u32(bytes, 16) != R6_ENMA_SIM_HITS ||
        r6_u32(bytes, 20) != R6_ENMA_SIM_CONFIG_SIZE ||
        r6_u32(bytes, 28) != R6_ENMA_SIM_CONFIG_OFF +
                             R6_ENMA_SIM_CONFIG_SIZE) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.getter_count = r6_u32(bytes, 12);
    header.hit_count = r6_u32(bytes, 16);
    header.config_size = r6_u32(bytes, 20);
    header.strings_size = r6_u32(bytes, 24);
    header.strings_off = r6_u32(bytes, 28);
    if (!header.strings_size ||
        (size_t)header.strings_off + header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int enma_name(const unsigned char *bytes, size_t size,
                     uint32_t strings_off, uint32_t offset, char *out,
                     size_t capacity) {
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

int r6_enma_sim_parse(const void *data, size_t size,
                      r6_enma_sim_header *out) {
    return enma_header(data, size, out);
}

int r6_enma_sim_getter(const void *data, size_t size, uint32_t index,
                       char *name, size_t name_capacity,
                       char *export_name, size_t export_capacity,
                       uint32_t *hit_first, uint32_t *hit_count,
                       uint32_t *baseline_kind, uint32_t *baseline_bits) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_sim_header header;
    uint32_t row_off;
    uint32_t first;
    uint32_t count;
    uint32_t expected = 0;
    uint32_t at;
    uint32_t kind;
    int result = enma_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.getter_count) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < index; at++) {
        expected += r6_u32(bytes, R6_ENMA_SIM_GETTER_OFF + at * 24u + 12u);
    }
    row_off = R6_ENMA_SIM_GETTER_OFF + index * 24u;
    first = r6_u32(bytes, row_off + 8u);
    count = r6_u32(bytes, row_off + 12u);
    kind = r6_u32(bytes, row_off + 16u);
    if (first != expected || first + count > header.hit_count ||
        kind > R6_ENMA_SIM_BASE_BOOL) {
        return R6_ERR_FORMAT;
    }
    result = enma_name(bytes, size, header.strings_off,
                       r6_u32(bytes, row_off), name, name_capacity);
    if (result != R6_OK) {
        return result;
    }
    result = enma_name(bytes, size, header.strings_off,
                       r6_u32(bytes, row_off + 4u), export_name,
                       export_capacity);
    if (result != R6_OK) {
        return result;
    }
    if (hit_first) {
        *hit_first = first;
    }
    if (hit_count) {
        *hit_count = count;
    }
    if (baseline_kind) {
        *baseline_kind = kind;
    }
    if (baseline_bits) {
        *baseline_bits = r6_u32(bytes, row_off + 20u);
    }
    return R6_OK;
}

int r6_enma_sim_hit(const void *data, size_t size, uint32_t index,
                    uint32_t *offset, uint32_t *value_bits) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_sim_header header;
    uint32_t row_off;
    int result = enma_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.hit_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_ENMA_SIM_HIT_OFF + index * 8u;
    if (r6_u32(bytes, row_off) >= R6_ENMA_SIM_CONFIG_SIZE) {
        return R6_ERR_FORMAT;
    }
    if (offset) {
        *offset = r6_u32(bytes, row_off);
    }
    if (value_bits) {
        *value_bits = r6_u32(bytes, row_off + 4u);
    }
    return R6_OK;
}

int r6_enma_sim_config(const void *data, size_t size, unsigned char *out,
                       size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_enma_sim_header header;
    int result = enma_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out || capacity < R6_ENMA_SIM_CONFIG_SIZE) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + R6_ENMA_SIM_CONFIG_OFF,
              R6_ENMA_SIM_CONFIG_SIZE);
    return R6_OK;
}
