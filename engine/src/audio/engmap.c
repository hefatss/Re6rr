/* Bounded WM4_ENGMAP text reader derived from tools/engine/audio_tables.py and
 * FUN_1407ccea0. No allocation, CRT or audio device. */

#include "r6/r6_engmap.h"

#include "core/internal.h"

static size_t engmap_line(const unsigned char *bytes, size_t size, size_t at,
                          size_t *begin, size_t *end) {
    while (at < size && (bytes[at] == ' ' || bytes[at] == '\t' ||
                         bytes[at] == '\r')) {
        at++;
    }
    *begin = at;
    while (at < size && bytes[at] != '\n' && bytes[at] != '\r') {
        at++;
    }
    *end = at;
    while (at < size && bytes[at] != '\n') {
        at++;
    }
    return at < size ? at + 1u : at;
}

static int engmap_integer(const unsigned char *bytes, size_t begin, size_t end,
                          int32_t *out) {
    size_t at = begin;
    int sign = 1;
    int32_t value = 0;
    while (at < end && (bytes[at] == ' ' || bytes[at] == '\t')) {
        at++;
    }
    if (at < end && (bytes[at] == '+' || bytes[at] == '-')) {
        if (bytes[at] == '-') {
            sign = -1;
        }
        at++;
    }
    if (at == end) {
        return 0;
    }
    while (at < end && bytes[at] >= '0' && bytes[at] <= '9') {
        int32_t digit = (int32_t)(bytes[at] - '0');
        if (value > (int32_t)(0x7FFFFFFFu - (uint32_t)digit) / 10) {
            return 0;
        }
        value = value * 10 + digit;
        at++;
    }
    while (at < end && (bytes[at] == ' ' || bytes[at] == '\t')) {
        at++;
    }
    if (at != end) {
        return 0;
    }
    *out = value * sign;
    return 1;
}

static int engmap_word(const unsigned char *bytes, size_t size, size_t at,
                       size_t *cursor, int32_t *out) {
    size_t begin;
    while (at < size && (bytes[at] == ' ' || bytes[at] == '\t')) {
        at++;
    }
    begin = at;
    while (at < size && bytes[at] != ' ' && bytes[at] != '\t' &&
           bytes[at] != '\r' && bytes[at] != '\n') {
        at++;
    }
    *cursor = at;
    return engmap_integer(bytes, begin, at, out);
}

int r6_engmap_parse(const void *text, size_t size, r6_engmap_t *out) {
    const unsigned char *bytes = (const unsigned char *)text;
    static const char magic[] = "WM4_ENGMAP";
    size_t line = 0;
    size_t begin;
    size_t end;
    int32_t count;
    int32_t value;
    uint32_t index;
    uint32_t pair;
    if (!bytes || !out || !size) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    line = engmap_line(bytes, size, line, &begin, &end);
    if (end - begin != sizeof(magic) - 1u ||
        r6_memcmp(bytes + begin, magic, sizeof(magic) - 1u) != 0) {
        return R6_ERR_FORMAT;
    }
    line = engmap_line(bytes, size, line, &begin, &end);
    if (!engmap_integer(bytes, begin, end, &count) || count <= 0 ||
        (uint32_t)count > R6_ENGMAP_MAX_PAIRS / (R6_ENGMAP_ENTRY_INTS / 2u)) {
        return R6_ERR_FORMAT;
    }
    out->count = (uint32_t)count;
    line = engmap_line(bytes, size, line, &begin, &end);
    for (index = 0; index < (uint32_t)count * R6_ENGMAP_ENTRY_INTS; index++) {
        if (!engmap_word(bytes, end, begin, &begin, &value)) {
            return R6_ERR_FORMAT;
        }
        pair = index / 2u;
        if (index % 2u == 0u) {
            out->pairs[pair].engine_sound = value;
        } else {
            out->pairs[pair].group = value;
        }
    }
    for (index = 0; index < out->count * 2u; index++) {
        for (pair = 0; pair < index; pair++) {
            if (out->pairs[index].engine_sound ==
                    out->pairs[pair].engine_sound &&
                out->pairs[index].group != out->pairs[pair].group) {
                r6_memset(out, 0, sizeof(*out));
                return R6_ERR_FORMAT;
            }
        }
    }
    return R6_OK;
}
