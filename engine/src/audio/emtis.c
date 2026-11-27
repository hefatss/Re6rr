/* Bounded EMTIS section reader derived from tools/engine/audio_tables.py.
 * Plain decimals and scientific notation are accepted; no CRT or libm. */

#include "r6/r6_emtis.h"

#include "core/internal.h"

#define R6_EMTIS_MARKER 60026.0

typedef struct emtis_cursor {
    const unsigned char *bytes;
    size_t at;
    size_t end;
} emtis_cursor;

static void emtis_line(const unsigned char *bytes, size_t size, size_t at,
                       emtis_cursor *line, size_t *next) {
    while (at < size && (bytes[at] == ' ' || bytes[at] == '\t' ||
                         bytes[at] == '\r')) {
        at++;
    }
    line->bytes = bytes;
    line->at = at;
    line->end = at;
    while (at < size && bytes[at] != '\n' && bytes[at] != '\r') {
        at++;
    }
    line->end = at;
    while (at < size && bytes[at] != '\n') {
        at++;
    }
    *next = at < size ? at + 1u : at;
}

static int emtis_space(unsigned char value) {
    return value == ' ' || value == '\t' || value == '\r' || value == '\n';
}

static int emtis_token(emtis_cursor *cursor, size_t *begin, size_t *end) {
    while (cursor->at < cursor->end &&
           emtis_space(cursor->bytes[cursor->at])) {
        cursor->at++;
    }
    if (cursor->at >= cursor->end) {
        return 0;
    }
    *begin = cursor->at;
    while (cursor->at < cursor->end &&
           !emtis_space(cursor->bytes[cursor->at])) {
        cursor->at++;
    }
    *end = cursor->at;
    return 1;
}

static int emtis_number(const unsigned char *bytes, size_t begin, size_t end,
                        double *out) {
    size_t at = begin;
    int sign = 1;
    double value = 0.0;
    int exponent = 0;
    int exponent_sign = 1;
    int is_float = 0;
    int digits = 0;
    if (at >= end) {
        return 0;
    }
    if (bytes[at] == '+' || bytes[at] == '-') {
        if (bytes[at] == '-') {
            sign = -1;
        }
        at++;
    }
    while (at < end && bytes[at] >= '0' && bytes[at] <= '9') {
        value = value * 10.0 + (double)(bytes[at] - '0');
        digits++;
        at++;
    }
    if (at < end && bytes[at] == '.') {
        double scale = 0.1;
        is_float = 1;
        at++;
        while (at < end && bytes[at] >= '0' && bytes[at] <= '9') {
            value += (double)(bytes[at] - '0') * scale;
            scale *= 0.1;
            digits++;
            at++;
        }
    }
    if (!digits) {
        return 0;
    }
    if (at < end && (bytes[at] == 'e' || bytes[at] == 'E')) {
        is_float = 1;
        at++;
        if (at < end && (bytes[at] == '+' || bytes[at] == '-')) {
            if (bytes[at] == '-') {
                exponent_sign = -1;
            }
            at++;
        }
        if (at == end) {
            return 0;
        }
        while (at < end && bytes[at] >= '0' && bytes[at] <= '9') {
            if (exponent < 10000) {
                exponent = exponent * 10 + (bytes[at] - '0');
            }
            at++;
        }
    }
    if (at != end) {
        return 0;
    }
    while (exponent > 0) {
        if (exponent_sign < 0) {
            value /= 10.0;
        } else {
            value *= 10.0;
        }
        exponent--;
    }
    *out = sign == 1 ? value : -value;
    (void)is_float;
    return 1;
}

static void emtis_section(r6_emtis_t *out, int32_t start, int32_t index) {
    r6_emtis_section_t *section;
    if (start < 0 || out->section_count >= R6_EMTIS_SECTION_MAX) {
        return;
    }
    section = &out->sections[out->section_count++];
    section->marker = start - 1;
    section->start = start;
    section->length = index - start;
}

static int emtis_hspace(unsigned char value) {
    return value == ' ' || value == '\t' || value == '\r';
}

static int emtis_name_line(const unsigned char *bytes, size_t size, size_t *at,
                           size_t *begin, size_t *end) {
    while (*at < size) {
        size_t cursor = *at;
        size_t first = *at;
        size_t last;
        while (cursor < size && bytes[cursor] != '\n' && bytes[cursor] != '\r') {
            cursor++;
        }
        last = cursor;
        while (first < last && emtis_hspace(bytes[first])) {
            first++;
        }
        while (last > first && emtis_hspace(bytes[last - 1u])) {
            last--;
        }
        while (cursor < size && bytes[cursor] != '\n') {
            cursor++;
        }
        *at = cursor < size ? cursor + 1u : cursor;
        if (first < last) {
            *begin = first;
            *end = last;
            return 1;
        }
    }
    return 0;
}

static size_t emtis_names_begin(const void *text, size_t size) {
    const unsigned char *bytes = (const unsigned char *)text;
    emtis_cursor cursor;
    size_t next = 0;
    emtis_line(bytes, size, next, &cursor, &next);
    emtis_line(bytes, size, next, &cursor, &next);
    emtis_line(bytes, size, next, &cursor, &next);
    emtis_line(bytes, size, next, &cursor, &next);
    return next;
}

static void emtis_names(const unsigned char *bytes, size_t begin, size_t size,
                        r6_emtis_t *out) {
    static const char *prefixes[R6_EMTIS_NAME_PREFIXES] = {
        "Missfire", "Turbin", "Intake", "Engine"
    };
    size_t at = begin;
    size_t first;
    size_t end;
    uint32_t index;
    while (emtis_name_line(bytes, size, &at, &first, &end)) {
        out->name_count++;
        for (index = 0; index < R6_EMTIS_NAME_PREFIXES; index++) {
            size_t length = 0;
            while (prefixes[index][length]) {
                length++;
            }
            if ((size_t)(end - first) >= length &&
                r6_memcmp(bytes + first, prefixes[index], length) == 0 &&
                (first + length == end || bytes[first + length] == '/')) {
                out->name_counts[index]++;
                break;
            }
        }
    }
}

int r6_emtis_parse(const void *text, size_t size, r6_emtis_t *out) {
    const unsigned char *bytes = (const unsigned char *)text;
    emtis_cursor head;
    emtis_cursor tokens;
    emtis_cursor line;
    size_t next = 0;
    size_t begin;
    size_t end;
    size_t second_end;
    size_t name_start;
    double value;
    int32_t start = -1;
    uint32_t head_count = 0;
    uint32_t index = 0;
    if (!bytes || !out || !size) {
        return R6_ERR_ARG;
    }
    r6_memset(out, 0, sizeof(*out));
    emtis_line(bytes, size, next, &head, &next);
    tokens.bytes = bytes;
    tokens.at = head.at;
    tokens.end = head.end;
    if (!emtis_token(&tokens, &begin, &end) ||
        (size_t)(end - begin) != 5u ||
        r6_memcmp(bytes + begin, "EMTIS", 5u) != 0) {
        return R6_ERR_FORMAT;
    }
    while (emtis_token(&tokens, &begin, &end)) {
        if (out->version_count >= R6_EMTIS_VERSION_MAX ||
            !emtis_number(bytes, begin, end, &value)) {
            return R6_ERR_FORMAT;
        }
        out->version[out->version_count++] = (uint32_t)value;
    }
    emtis_line(bytes, size, next, &line, &next);
    tokens.at = line.at;
    tokens.end = line.end;
    while (emtis_token(&tokens, &begin, &end)) {
        if (out->header_count >= R6_EMTIS_HEADER_MAX ||
            !emtis_number(bytes, begin, end, &value)) {
            return R6_ERR_FORMAT;
        }
        out->header[out->header_count++] = value;
    }
    emtis_line(bytes, size, next, &tokens, &next);
    emtis_line(bytes, size, next, &line, &second_end);
    name_start = second_end;
    tokens.end = line.end;
    while (emtis_token(&tokens, &begin, &end)) {
        if (!emtis_number(bytes, begin, end, &value)) {
            return R6_ERR_FORMAT;
        }
        if (value == R6_EMTIS_MARKER) {
            emtis_section(out, start, (int32_t)index);
            start = (int32_t)index + 1;
            head_count = 0;
        } else if (start >= 0 && head_count < R6_EMTIS_SECTION_HEAD &&
                   out->section_count < R6_EMTIS_SECTION_MAX) {
            out->sections[out->section_count].head[head_count++] = value;
        }
        index++;
    }
    emtis_section(out, start, (int32_t)index);
    out->token_count = index;
    emtis_names(bytes, name_start, size, out);
    return R6_OK;
}

int r6_emtis_name(const void *text, size_t size, uint32_t index,
                  char *name, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)text;
    r6_emtis_t table;
    size_t at;
    size_t begin;
    size_t end;
    uint32_t count = 0;
    int result = r6_emtis_parse(text, size, &table);
    if (result != R6_OK) {
        return result;
    }
    if (!name || !capacity) {
        return R6_ERR_ARG;
    }
    if (index >= table.name_count) {
        return R6_ERR_ARG;
    }
    at = emtis_names_begin(text, size);
    while (count < table.name_count &&
           emtis_name_line(bytes, size, &at, &begin, &end)) {
        if (count == index) {
            size_t length = end - begin;
            if (length + 1u > capacity) {
                return R6_ERR_BUFFER;
            }
            r6_memcpy(name, bytes + begin, length);
            name[length] = 0;
            return R6_OK;
        }
        count++;
    }
    return R6_ERR_FORMAT;
}

int r6_emtis_find_name(const void *text, size_t size, const char *name,
                       uint32_t *index) {
    const unsigned char *bytes = (const unsigned char *)text;
    r6_emtis_t table;
    size_t at;
    size_t begin;
    size_t end;
    size_t wanted;
    uint32_t count = 0;
    int result = r6_emtis_parse(text, size, &table);
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
    at = emtis_names_begin(text, size);
    while (count < table.name_count &&
           emtis_name_line(bytes, size, &at, &begin, &end)) {
        if (end - begin == wanted &&
            r6_memcmp(bytes + begin, name, wanted) == 0) {
            if (index) {
                *index = count;
            }
            return R6_OK;
        }
        count++;
    }
    return R6_ERR_NOT_FOUND;
}
