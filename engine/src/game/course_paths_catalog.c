/* Bounds-checked reader for packed course route and path-bin facts. Only
 * copied strings and numbers cross the bridge; path geometry is not read. */

#include "r6/r6_course_paths_catalog.h"

#include "core/internal.h"

enum {
    R6_COURSE_PATHS_HEADER_SIZE = 28,
    R6_COURSE_PATHS_ROUTE_SIZE = 28,
    R6_COURSE_PATHS_REF_SIZE = 8,
    R6_COURSE_PATHS_FILE_SIZE = 16,
    R6_COURSE_PATHS_STRIDE = 12
};

static const unsigned char course_paths_magic[8] = {
    'R', '6', 'C', 'P', 'S', 0, 1, 0
};

static int course_paths_layout(const void *data, size_t size,
                               r6_course_paths_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_paths_header_t header;
    size_t routes;
    size_t refs;
    size_t files;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_COURSE_PATHS_HEADER_SIZE ||
            r6_memcmp(bytes, course_paths_magic,
                      sizeof(course_paths_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.route_count = r6_u32(bytes, 12);
    header.ref_count = r6_u32(bytes, 16);
    header.file_count = r6_u32(bytes, 20);
    if (header.route_count > ((size_t)-1 - R6_COURSE_PATHS_HEADER_SIZE) /
                             R6_COURSE_PATHS_ROUTE_SIZE ||
            header.ref_count > ((size_t)-1 - R6_COURSE_PATHS_HEADER_SIZE -
                                (size_t)header.route_count *
                                R6_COURSE_PATHS_ROUTE_SIZE) /
                               R6_COURSE_PATHS_REF_SIZE ||
            header.file_count > ((size_t)-1 - R6_COURSE_PATHS_HEADER_SIZE -
                                 (size_t)header.route_count *
                                 R6_COURSE_PATHS_ROUTE_SIZE -
                                 (size_t)header.ref_count *
                                 R6_COURSE_PATHS_REF_SIZE) /
                                R6_COURSE_PATHS_FILE_SIZE) {
        return R6_ERR_FORMAT;
    }
    routes = (size_t)header.route_count * R6_COURSE_PATHS_ROUTE_SIZE;
    refs = (size_t)header.ref_count * R6_COURSE_PATHS_REF_SIZE;
    files = (size_t)header.file_count * R6_COURSE_PATHS_FILE_SIZE;
    header.strings_size = r6_u32(bytes, 24);
    if (!header.route_count || !header.ref_count || !header.file_count ||
            !header.strings_size ||
            (size_t)R6_COURSE_PATHS_HEADER_SIZE + routes + refs + files > size ||
            (size_t)R6_COURSE_PATHS_HEADER_SIZE + routes + refs + files +
            header.strings_size != size) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static int course_paths_string(const void *data, size_t size, uint32_t offset,
                               char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_course_paths_header_t header;
    size_t strings_off;
    size_t end;
    uint32_t at;
    int result = course_paths_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    strings_off = R6_COURSE_PATHS_HEADER_SIZE +
                  (size_t)header.route_count * R6_COURSE_PATHS_ROUTE_SIZE +
                  (size_t)header.ref_count * R6_COURSE_PATHS_REF_SIZE +
                  (size_t)header.file_count * R6_COURSE_PATHS_FILE_SIZE;
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

int r6_course_paths_parse(const void *data, size_t size,
                          r6_course_paths_header_t *out) {
    return course_paths_layout(data, size, out);
}

int r6_course_paths_file(const void *data, size_t size, uint32_t index,
                         r6_course_paths_file_t *out) {
    const unsigned char *bytes;
    r6_course_paths_header_t header;
    uint32_t row;
    int result = course_paths_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count || !out) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_COURSE_PATHS_HEADER_SIZE +
                     (size_t)header.route_count * R6_COURSE_PATHS_ROUTE_SIZE +
                     (size_t)header.ref_count * R6_COURSE_PATHS_REF_SIZE +
                     (size_t)index * R6_COURSE_PATHS_FILE_SIZE);
    out->file_size = r6_u32(bytes, row + 8);
    out->triple_count = r6_u32(bytes, row + 12);
    if (!out->triple_count ||
            (uint64_t)out->triple_count * R6_COURSE_PATHS_STRIDE !=
            out->file_size) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_course_paths_path(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_course_paths_header_t header;
    uint32_t row;
    int result = course_paths_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.file_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_COURSE_PATHS_HEADER_SIZE +
                     (size_t)header.route_count * R6_COURSE_PATHS_ROUTE_SIZE +
                     (size_t)header.ref_count * R6_COURSE_PATHS_REF_SIZE +
                     (size_t)index * R6_COURSE_PATHS_FILE_SIZE);
    return course_paths_string(data, size, r6_u32(bytes, row), out, capacity);
}

int r6_course_paths_route(const void *data, size_t size, uint32_t index,
                          r6_course_paths_route_t *out) {
    const unsigned char *bytes;
    r6_course_paths_header_t header;
    uint32_t row;
    int result = course_paths_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.route_count || !out) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_COURSE_PATHS_HEADER_SIZE +
                     (size_t)index * R6_COURSE_PATHS_ROUTE_SIZE);
    out->area_id = r6_u32(bytes, row + 8);
    out->loop = r6_u32(bytes, row + 12);
    out->camera_direction = r6_u32(bytes, row + 16);
    out->path_first = r6_u32(bytes, row + 20);
    out->path_count = r6_u32(bytes, row + 24);
    if (!out->path_count || out->path_first > header.ref_count ||
            out->path_count > header.ref_count - out->path_first ||
            out->loop > 1u || out->camera_direction > 1u) {
        return R6_ERR_FORMAT;
    }
    if (index + 1u < header.route_count) {
        uint32_t next_first = r6_u32(bytes, row + R6_COURSE_PATHS_ROUTE_SIZE +
                                     20);
        if (out->path_first > next_first ||
                next_first - out->path_first != out->path_count) {
            return R6_ERR_FORMAT;
        }
    } else if (out->path_first != header.ref_count - out->path_count) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

int r6_course_paths_route_name(const void *data, size_t size, uint32_t index,
                               char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_course_paths_header_t header;
    uint32_t row;
    int result = course_paths_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.route_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_COURSE_PATHS_HEADER_SIZE +
                     (size_t)index * R6_COURSE_PATHS_ROUTE_SIZE);
    return course_paths_string(data, size, r6_u32(bytes, row), out, capacity);
}

int r6_course_paths_route_ref(const void *data, size_t size, uint32_t index,
                              char *out, size_t capacity) {
    const unsigned char *bytes;
    r6_course_paths_header_t header;
    uint32_t row;
    int result = course_paths_layout(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.ref_count) {
        return R6_ERR_ARG;
    }
    bytes = (const unsigned char *)data;
    row = (uint32_t)(R6_COURSE_PATHS_HEADER_SIZE +
                     (size_t)header.route_count * R6_COURSE_PATHS_ROUTE_SIZE +
                     (size_t)index * R6_COURSE_PATHS_REF_SIZE);
    return course_paths_string(data, size, r6_u32(bytes, row), out, capacity);
}
