/* Bounded reader for the derived string-pointer-run inventory. The core only
 * copies facts from the supplied blob; it never reads the executable. */

#include "r6/r6_name_runs.h"

#include "core/internal.h"

static const unsigned char name_runs_magic[8] = {
    'R', '6', 'N', 'T', 'R', 0, 1, 0
};

enum {
    R6_NAME_RUNS_HEADER_SIZE = 28,
    R6_NAME_RUNS_RUN_OFF = 28,
    R6_NAME_RUNS_USER_OFF = R6_NAME_RUNS_RUN_OFF + R6_NAME_RUNS_RUNS * 28u,
    R6_NAME_RUNS_NAME_OFF = R6_NAME_RUNS_USER_OFF + R6_NAME_RUNS_USERS * 4u,
    R6_NAME_RUNS_STRING_OFF = R6_NAME_RUNS_NAME_OFF +
                              R6_NAME_RUNS_NAMES * 4u
};

static int name_runs_header(const void *data, size_t size,
                            r6_name_runs_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_name_runs_header header;
    if (!bytes || !out || size < R6_NAME_RUNS_HEADER_SIZE ||
        r6_memcmp(bytes, name_runs_magic,
                  sizeof(name_runs_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_NAME_RUNS_RUNS ||
        r6_u32(bytes, 16) != R6_NAME_RUNS_NAMES ||
        r6_u32(bytes, 20) != R6_NAME_RUNS_USERS) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.run_count = r6_u32(bytes, 12);
    header.name_count = r6_u32(bytes, 16);
    header.user_count = r6_u32(bytes, 20);
    header.strings_size = r6_u32(bytes, 24);
    if (!header.strings_size ||
        (size_t)R6_NAME_RUNS_STRING_OFF + header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int name_runs_string(const void *data, size_t size, uint32_t offset,
                            char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t at = offset;
    if (!out || !capacity) {
        return R6_ERR_ARG;
    }
    if (offset < R6_NAME_RUNS_STRING_OFF || offset >= size) {
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

int r6_name_runs_parse(const void *data, size_t size,
                       r6_name_runs_header *out) {
    return name_runs_header(data, size, out);
}

int r6_name_runs_run(const void *data, size_t size, uint32_t index,
                     uint32_t *rva, uint32_t *table_size, uint32_t *stride,
                     uint32_t *count, uint32_t *name_first,
                     uint32_t *user_first, uint32_t *user_count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_name_runs_header header;
    uint32_t row_off;
    uint32_t first;
    uint32_t users;
    uint32_t number;
    uint32_t step;
    int result = name_runs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.run_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_NAME_RUNS_RUN_OFF + index * 28u;
    first = r6_u32(bytes, row_off + 16u);
    users = r6_u32(bytes, row_off + 24u);
    number = r6_u32(bytes, row_off + 12u);
    step = r6_u32(bytes, row_off + 8u);
    if (r6_u32(bytes, row_off + 4u) != number * step ||
        first + number > header.name_count ||
        r6_u32(bytes, row_off + 20u) + users > header.user_count) {
        return R6_ERR_FORMAT;
    }
    if (rva) {
        *rva = r6_u32(bytes, row_off);
    }
    if (table_size) {
        *table_size = r6_u32(bytes, row_off + 4u);
    }
    if (stride) {
        *stride = step;
    }
    if (count) {
        *count = number;
    }
    if (name_first) {
        *name_first = first;
    }
    if (user_first) {
        *user_first = r6_u32(bytes, row_off + 20u);
    }
    if (user_count) {
        *user_count = users;
    }
    return R6_OK;
}

int r6_name_runs_name(const void *data, size_t size, uint32_t index,
                      char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_name_runs_header header;
    uint32_t offset;
    int result = name_runs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.name_count) {
        return R6_ERR_ARG;
    }
    offset = r6_u32(bytes, R6_NAME_RUNS_NAME_OFF + index * 4u);
    return name_runs_string(data, size, offset, out, capacity);
}

int r6_name_runs_run_name(const void *data, size_t size, uint32_t run_index,
                          uint32_t local_index, char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t first = 0;
    uint32_t count = 0;
    int result = r6_name_runs_run(data, size, run_index, NULL, NULL, NULL,
                                  &count, &first, NULL, NULL);
    if (result != R6_OK) {
        return result;
    }
    if (local_index >= count) {
        return R6_ERR_ARG;
    }
    return r6_name_runs_name(
        data, size, first + local_index, out, capacity);
}

int r6_name_runs_user(const void *data, size_t size, uint32_t index,
                      uint32_t *rva) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_name_runs_header header;
    int result = name_runs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.user_count) {
        return R6_ERR_ARG;
    }
    if (rva) {
        *rva = r6_u32(bytes, R6_NAME_RUNS_USER_OFF + index * 4u);
    }
    return R6_OK;
}

int r6_name_runs_find(const void *data, size_t size, const char *name,
                      uint32_t *run_index, uint32_t *local_index,
                      uint32_t *global_index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_name_runs_header header;
    size_t wanted;
    uint32_t local = 0;
    uint32_t global = 0;
    uint32_t at;
    int result = name_runs_header(data, size, &header);
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
    for (at = 0; at < header.run_count; at++) {
        uint32_t count = r6_u32(bytes, R6_NAME_RUNS_RUN_OFF + at * 28u + 12u);
        for (local = 0; local < count; local++) {
            uint32_t offset = r6_u32(bytes,
                                     R6_NAME_RUNS_NAME_OFF + global * 4u);
            uint32_t end = offset;
            while (end < size && bytes[end]) {
                end++;
            }
            if (end < size && end - offset == wanted &&
                r6_memcmp(bytes + offset, name, wanted) == 0) {
                if (run_index) {
                    *run_index = at;
                }
                if (local_index) {
                    *local_index = local;
                }
                if (global_index) {
                    *global_index = global;
                }
                return R6_OK;
            }
            global++;
        }
    }
    return R6_ERR_NOT_FOUND;
}

int r6_name_runs_find_user(const void *data, size_t size, uint32_t rva,
                           uint32_t *index) {
    r6_name_runs_header header;
    uint32_t at;
    int result = name_runs_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    for (at = 0; at < header.user_count; at++) {
        uint32_t found = 0;
        result = r6_name_runs_user(data, size, at, &found);
        if (result == R6_ERR_ARG) {
            return R6_ERR_FORMAT;
        }
        if (result != R6_OK) {
            return result;
        }
        if (found == rva) {
            if (index) {
                *index = at;
            }
            return R6_OK;
        }
    }
    return R6_ERR_NOT_FOUND;
}
