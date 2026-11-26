/* Bounded reader for the derived reference-word xref inventory. */

#include "r6/r6_ref_words.h"

#include "core/internal.h"

static const unsigned char ref_words_magic[8] = {
    'R', '6', 'R', 'E', 'F', 0, 1, 0
};

enum {
    R6_REF_HEADER_SIZE = 20,
    R6_REF_WORD_OFF = 20,
    R6_REF_XREF_OFF = R6_REF_WORD_OFF + R6_REF_WORDS_COUNT * 12u
};

static int ref_header(const void *data, size_t size,
                      r6_ref_words_header *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ref_words_header header;
    if (!bytes || !out || size < R6_REF_HEADER_SIZE ||
        r6_memcmp(bytes, ref_words_magic, sizeof(ref_words_magic)) != 0 ||
        r6_u32(bytes, 8) != 1u ||
        r6_u32(bytes, 12) != R6_REF_WORDS_COUNT ||
        r6_u32(bytes, 16) != R6_REF_XREFS ||
        size != R6_REF_XREF_OFF + R6_REF_XREFS * 4u) {
        return R6_ERR_FORMAT;
    }
    header.version = r6_u32(bytes, 8);
    header.word_count = r6_u32(bytes, 12);
    header.xref_count = r6_u32(bytes, 16);
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_ref_words_parse(const void *data, size_t size,
                       r6_ref_words_header *out) {
    return ref_header(data, size, out);
}

int r6_ref_words_word(const void *data, size_t size, uint32_t index,
                      uint32_t *value, uint32_t *xref_first,
                      uint32_t *xref_count) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ref_words_header header;
    uint32_t row_off;
    uint32_t first;
    uint32_t count;
    int result = ref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.word_count) {
        return R6_ERR_ARG;
    }
    row_off = R6_REF_WORD_OFF + index * 12u;
    first = r6_u32(bytes, row_off + 4u);
    count = r6_u32(bytes, row_off + 8u);
    if (first + count > header.xref_count ||
        (index && r6_u32(bytes, row_off - 12u) >= r6_u32(bytes, row_off))) {
        return R6_ERR_FORMAT;
    }
    if (value) {
        *value = r6_u32(bytes, row_off);
    }
    if (xref_first) {
        *xref_first = first;
    }
    if (xref_count) {
        *xref_count = count;
    }
    return R6_OK;
}

int r6_ref_words_xref(const void *data, size_t size, uint32_t index,
                      uint32_t *rva) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ref_words_header header;
    uint32_t value;
    int result = ref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.xref_count) {
        return R6_ERR_ARG;
    }
    value = r6_u32(bytes, R6_REF_XREF_OFF + index * 4u);
    if (value < 0x1000u || value >= 34308096u) {
        return R6_ERR_FORMAT;
    }
    if (rva) {
        *rva = value;
    }
    return R6_OK;
}

int r6_ref_words_word_xref(const void *data, size_t size,
                           uint32_t word_index, uint32_t local_index,
                           uint32_t *rva) {
    uint32_t first = 0;
    uint32_t count = 0;
    int result = r6_ref_words_word(data, size, word_index, NULL, &first,
                                   &count);
    if (result != R6_OK) {
        return result;
    }
    if (local_index >= count) {
        return R6_ERR_ARG;
    }
    return r6_ref_words_xref(data, size, first + local_index, rva);
}

int r6_ref_words_find(const void *data, size_t size, uint32_t value,
                      uint32_t *word_index) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_ref_words_header header;
    uint32_t low = 0;
    uint32_t high;
    int result = ref_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    high = header.word_count;
    while (low < high) {
        uint32_t mid = low + (high - low) / 2u;
        uint32_t found = r6_u32(bytes, R6_REF_WORD_OFF + mid * 12u);
        if (found < value) {
            low = mid + 1u;
        } else {
            high = mid;
        }
    }
    if (low == header.word_count ||
        r6_u32(bytes, R6_REF_WORD_OFF + low * 12u) != value) {
        return R6_ERR_NOT_FOUND;
    }
    if (word_index) {
        *word_index = low;
    }
    return R6_OK;
}
