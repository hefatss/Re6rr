/* gzip (RFC 1952) inflation for the asset containers in the dump.
 *
 * Uses vendored miniz 2.2.0 in raw-deflate mode. miniz's zlib wrapper has no
 * gzip support, so the header is parsed here. The decompressor state comes
 * from one static scratch block: inflation is strictly sequential, which
 * matches the loader. No heap and no CRT are needed.
 */

#include "core/internal.h"
#include "r6/r6_asset.h"

#include "miniz.h"

/* Enough for miniz's inflate_state (32 KiB dictionary + bookkeeping). */
static union {
    unsigned char bytes[64 * 1024];
    mz_uint64 align;
} r6_inflate_state;

static int r6_inflate_state_busy;

static void *r6_zalloc(void *opaque, size_t items, size_t size) {
    (void)opaque;
    if (r6_inflate_state_busy || items == 0 ||
        size > sizeof(r6_inflate_state.bytes) / items) {
        return 0;
    }
    r6_inflate_state_busy = 1;
    return r6_inflate_state.bytes;
}

static void r6_zfree(void *opaque, void *address) {
    (void)opaque;
    if (address == r6_inflate_state.bytes) {
        r6_inflate_state_busy = 0;
    }
}

/* Returns the offset of the deflate payload, or 0 on a malformed header. */
static size_t gzip_payload(const unsigned char *bytes, size_t size) {
    size_t at;
    unsigned flags;
    if (size < 18 || bytes[0] != 0x1f || bytes[1] != 0x8b ||
        bytes[2] != 8) {
        return 0;
    }
    flags = bytes[3];
    if (flags & 0xe0) {
        return 0;
    }
    at = 10;
    if (flags & 4) {
        size_t extra;
        if (at + 2 > size) {
            return 0;
        }
        extra = (size_t)bytes[at] | ((size_t)bytes[at + 1] << 8);
        at += 2;
        if (at + extra > size) {
            return 0;
        }
        at += extra;
    }
    if (flags & 8) {
        while (at < size && bytes[at]) {
            at++;
        }
        if (at >= size) {
            return 0;
        }
        at++;
    }
    if (flags & 16) {
        while (at < size && bytes[at]) {
            at++;
        }
        if (at >= size) {
            return 0;
        }
        at++;
    }
    if (flags & 2) {
        at += 2;
    }
    /* 8-byte gzip trailer: CRC32 + ISIZE. */
    return (at + 8 <= size) ? at : 0;
}

int r6_gzip_expected_size(const void *data, size_t size, size_t *out_size) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t at;
    if (!data || !out_size) {
        return R6_ERR_ARG;
    }
    at = gzip_payload(bytes, size);
    if (at == 0) {
        return R6_ERR_FORMAT;
    }
    *out_size = (size_t)bytes[size - 4] |
                ((size_t)bytes[size - 3] << 8) |
                ((size_t)bytes[size - 2] << 16) |
                ((size_t)bytes[size - 1] << 24);
    return R6_OK;
}

int r6_gzip_inflate(const void *data, size_t size, void *out,
                    size_t capacity, size_t *out_size) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t at;
    size_t expected = 0;
    size_t payload;
    mz_stream stream;
    int rc;
    size_t written;
    if (!data || !out_size) {
        return R6_ERR_ARG;
    }
    *out_size = 0;
    at = gzip_payload(bytes, size);
    if (at == 0) {
        return R6_ERR_FORMAT;
    }
    rc = r6_gzip_expected_size(data, size, &expected);
    if (rc != R6_OK) {
        return rc;
    }
    if (expected > capacity) {
        *out_size = expected;
        return R6_ERR_BUFFER;
    }
    payload = size - at - 8;
    if (r6_inflate_state_busy) {
        return R6_ERR_BUFFER;
    }
    r6_memset(&stream, 0, sizeof(stream));
    stream.zalloc = r6_zalloc;
    stream.zfree = r6_zfree;
    stream.next_in = bytes + at;
    stream.avail_in = (mz_uint)payload;
    stream.next_out = (unsigned char *)out;
    stream.avail_out = (mz_uint)capacity;
    if (mz_inflateInit2(&stream, -MZ_DEFAULT_WINDOW_BITS) != MZ_OK) {
        return R6_ERR_FORMAT;
    }
    rc = mz_inflate(&stream, MZ_FINISH);
    written = (size_t)stream.total_out;
    mz_inflateEnd(&stream);
    if (rc != MZ_STREAM_END || written != expected) {
        return R6_ERR_FORMAT;
    }
    *out_size = written;
    return R6_OK;
}
