#include "core/internal.h"
#include "r6/r6_asset.h"

int r6_xmd_parse(const void *data, size_t size, r6_stream *out,
                 size_t capacity, uint32_t *version, uint32_t *count) {
    static const unsigned char magic[7] = {
        'X', 'M', 'D', 0x00, '0', '0', '1'
    };
    uint32_t streams;
    uint32_t i;
    if (!data || size < 16 || r6_memcmp(data, magic, 7) != 0) {
        return R6_ERR_FORMAT;
    }
    streams = r6_u32(data, 0x0C);
    if (0x10 + (size_t)streams * 4 > size) {
        return R6_ERR_FORMAT;
    }
    if (version) {
        *version = r6_u32(data, 0x08);
    }
    if (count) {
        *count = streams;
    }
    if (capacity < streams) {
        return R6_ERR_BUFFER;
    }
    for (i = 0; i < streams; i++) {
        uint32_t start = r6_u32(data, 0x10 + (size_t)i * 4);
        uint32_t end = (i + 1 < streams)
                           ? r6_u32(data, 0x10 + (size_t)(i + 1) * 4)
                           : (uint32_t)size;
        if (start >= size || end > size || end < start) {
            return R6_ERR_FORMAT;
        }
        if (out) {
            out[i].offset = start;
            out[i].size = end - start;
        }
    }
    return R6_OK;
}
