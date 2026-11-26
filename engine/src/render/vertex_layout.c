/* Bounds-checked reader for compiled vertex-input layouts. */

#include "core/internal.h"
#include "r6/r6_vertex_layout.h"

static const unsigned char vertex_magic[4] = {'R', '6', 'G', 'V'};

int r6_vertex_init(r6_vertex_view *view, const void *data, size_t size) {
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t count;
    uint32_t strings;
    uint64_t required;
    if (!view || !bytes || size < R6_VERTEX_HEADER_SIZE ||
        r6_memcmp(bytes, vertex_magic, sizeof(vertex_magic)) != 0 ||
        r6_u16(bytes, 4) != 1u || r6_u16(bytes, 6) != 0u ||
        r6_u32(bytes, 16) != 0u || r6_u32(bytes, 20) != 0u) {
        return R6_ERR_FORMAT;
    }
    count = r6_u32(bytes, 8);
    strings = r6_u32(bytes, 12);
    required = R6_VERTEX_HEADER_SIZE + (uint64_t)count *
               R6_VERTEX_RECORD_SIZE;
    if (strings != required || strings >= size || bytes[size - 1] != 0) {
        return R6_ERR_FORMAT;
    }
    view->data = bytes;
    view->size = size;
    view->count = count;
    view->strings = strings;
    return R6_OK;
}

const char *r6_vertex_name(const r6_vertex_view *view, uint32_t offset) {
    const char *text;
    size_t i;
    if (!view || offset >= view->size || offset < view->strings) {
        return NULL;
    }
    text = (const char *)view->data + offset;
    for (i = 0; offset + i < view->size && text[i]; i++) {
        /* scan for the terminator inside the caller-owned blob */
    }
    return offset + i < view->size ? text : NULL;
}

int r6_vertex_get_attrib(const r6_vertex_view *view, uint32_t index,
                         r6_vertex_attrib *out) {
    const unsigned char *at;
    if (!view || !out || index >= view->count) {
        return R6_ERR_ARG;
    }
    at = view->data + R6_VERTEX_HEADER_SIZE +
         (size_t)index * R6_VERTEX_RECORD_SIZE;
    r6_memcpy(out, at, R6_VERTEX_RECORD_SIZE);
    return R6_OK;
}

static int vertex_name_eq(const r6_vertex_view *view, uint32_t offset,
                          const char *text) {
    const char *name = r6_vertex_name(view, offset);
    size_t i;
    if (!name || !text) {
        return 0;
    }
    for (i = 0; name[i] && text[i] && i < view->size; i++) {
        if (name[i] != text[i]) {
            return 0;
        }
    }
    return i < view->size && name[i] == text[i];
}

int r6_vertex_find(const r6_vertex_view *view, const char *shader,
                   uint16_t location, r6_vertex_attrib *out) {
    r6_vertex_attrib item;
    uint32_t i;
    if (!view || !shader || !out) {
        return R6_ERR_ARG;
    }
    for (i = 0; i < view->count; i++) {
        if (r6_vertex_get_attrib(view, i, &item) != R6_OK ||
            item.location != location ||
            !vertex_name_eq(view, item.shader_off, shader)) {
            continue;
        }
        *out = item;
        return R6_OK;
    }
    return R6_ERR_NOT_FOUND;
}
