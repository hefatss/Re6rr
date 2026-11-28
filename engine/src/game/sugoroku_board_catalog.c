/* Bounds-checked reader for packed sugoroku board facts. */

#include "r6/r6_sugoroku_board_catalog.h"

#include "core/internal.h"

enum {
    R6_SGR_HEADER_SIZE = 40,
    R6_SGR_CATEGORY_SIZE = 24,
    R6_SGR_PAGE_SIZE = 64,
    R6_SGR_FUNCTION_SIZE = 8,
    R6_SGR_CATEGORIES = 6,
    R6_SGR_STAGES = 7,
    R6_SGR_PAGES = 14,
    R6_SGR_FUNCTIONS = 6,
    R6_SGR_ITEMS = 115,
    R6_SGR_SQUARES = 361
};

static const unsigned char sgr_magic[8] = {
    'R', '6', 'S', 'G', 'R', 0, 1, 0
};

static int sgr_header(const void *data, size_t size,
                      r6_sugoroku_header_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sugoroku_header_t header;
    size_t base;
    if (!bytes || !out) {
        return R6_ERR_ARG;
    }
    if (size < R6_SGR_HEADER_SIZE ||
            r6_memcmp(bytes, sgr_magic, sizeof(sgr_magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    header.version = 1u;
    header.category_count = r6_u32(bytes, 12);
    header.stage_count = r6_u32(bytes, 16);
    header.page_count = r6_u32(bytes, 20);
    header.function_count = r6_u32(bytes, 24);
    header.item_count = r6_u32(bytes, 28);
    header.square_count = r6_u32(bytes, 32);
    header.string_size = r6_u32(bytes, 36);
    if (header.category_count != R6_SGR_CATEGORIES ||
            header.stage_count != R6_SGR_STAGES ||
            header.page_count != R6_SGR_PAGES ||
            header.function_count != R6_SGR_FUNCTIONS ||
            header.item_count != R6_SGR_ITEMS ||
            header.square_count != R6_SGR_SQUARES ||
            !header.string_size) {
        return R6_ERR_FORMAT;
    }
    base = R6_SGR_HEADER_SIZE +
           (size_t)header.category_count * R6_SGR_CATEGORY_SIZE +
           (size_t)header.page_count * R6_SGR_PAGE_SIZE +
           (size_t)header.function_count * R6_SGR_FUNCTION_SIZE;
    if (base > (size_t)-1 - header.string_size ||
            base + header.string_size != size) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

static size_t sgr_strings_base(const r6_sugoroku_header_t *header) {
    return R6_SGR_HEADER_SIZE +
           (size_t)header->category_count * R6_SGR_CATEGORY_SIZE +
           (size_t)header->page_count * R6_SGR_PAGE_SIZE +
           (size_t)header->function_count * R6_SGR_FUNCTION_SIZE;
}

static int sgr_string(const void *data, const r6_sugoroku_header_t *header,
                      uint32_t offset, uint32_t length) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t base = sgr_strings_base(header);
    size_t end = base + header->string_size;
    size_t at;
    if (!length || length > 64 || (size_t)offset < base ||
            (size_t)offset >= end ||
            (size_t)length > end - (size_t)offset - 1u) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < length; at++) {
        if (bytes[(size_t)offset + at] >= 0x80u) {
            return R6_ERR_FORMAT;
        }
    }
    if (bytes[(size_t)offset + length] != 0) {
        return R6_ERR_FORMAT;
    }
    return R6_OK;
}

static int sgr_category(const void *data, size_t size, uint32_t index,
                        r6_sugoroku_category_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sugoroku_header_t header;
    r6_sugoroku_category_t row;
    size_t at;
    int result = sgr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.category_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_SGR_HEADER_SIZE + (size_t)index * R6_SGR_CATEGORY_SIZE;
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (!row.groups || !row.ids || row.ids < row.groups ||
            row.id_min > row.id_max ||
            sgr_string(data, &header, row.name_offset, row.name_length) !=
                R6_OK) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int sgr_page(const void *data, size_t size, uint32_t index,
                    r6_sugoroku_page_t *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sugoroku_header_t header;
    r6_sugoroku_page_t row;
    uint32_t tokens = 0;
    uint32_t rewards = 0;
    size_t at;
    int result = sgr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.page_count || !out) {
        return R6_ERR_ARG;
    }
    at = R6_SGR_HEADER_SIZE + (size_t)header.category_count *
         R6_SGR_CATEGORY_SIZE + (size_t)index * R6_SGR_PAGE_SIZE;
    r6_memcpy(&row, bytes + at, sizeof(row));
    if (!row.stage || row.stage > header.stage_count || !row.page ||
            !row.squares) {
        return R6_ERR_FORMAT;
    }
    for (at = 0; at < 7; at++) {
        tokens += row.tokens[at];
    }
    for (at = 0; at < 6; at++) {
        rewards += row.rewards[at];
    }
    if (tokens != row.squares || rewards > row.squares) {
        return R6_ERR_FORMAT;
    }
    if (index) {
        r6_sugoroku_page_t previous;
        result = sgr_page(data, size, index - 1u, &previous);
        if (result != R6_OK || row.stage < previous.stage ||
                (row.stage == previous.stage && row.page <= previous.page)) {
            return R6_ERR_FORMAT;
        }
    }
    r6_memcpy(out, &row, sizeof(row));
    return R6_OK;
}

static int sgr_function(const void *data, size_t size, uint32_t index,
                        char *out, size_t capacity) {
    const unsigned char *bytes = (const unsigned char *)data;
    r6_sugoroku_header_t header;
    uint32_t offset;
    uint32_t length;
    size_t at;
    int result = sgr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (index >= header.function_count) {
        return R6_ERR_ARG;
    }
    at = R6_SGR_HEADER_SIZE +
         (size_t)header.category_count * R6_SGR_CATEGORY_SIZE +
         (size_t)header.page_count * R6_SGR_PAGE_SIZE +
         (size_t)index * R6_SGR_FUNCTION_SIZE;
    offset = r6_u32(bytes, at);
    length = r6_u32(bytes, at + 4);
    result = sgr_string(data, &header, offset, length);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    if ((size_t)length + 1u > capacity) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, bytes + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_sugoroku_parse(const void *data, size_t size,
                      r6_sugoroku_header_t *out) {
    r6_sugoroku_header_t header;
    r6_sugoroku_category_t category;
    r6_sugoroku_page_t page;
    uint32_t ids = 0;
    uint32_t squares = 0;
    uint32_t at;
    int result = sgr_header(data, size, &header);
    if (result != R6_OK) {
        return result;
    }
    if (!out) {
        return R6_ERR_ARG;
    }
    for (at = 0; at < header.category_count; at++) {
        result = sgr_category(data, size, at, &category);
        if (result != R6_OK || category.ids > header.item_count ||
                ids > header.item_count - category.ids) {
            return R6_ERR_FORMAT;
        }
        ids += category.ids;
    }
    for (at = 0; at < header.page_count; at++) {
        result = sgr_page(data, size, at, &page);
        if (result != R6_OK || page.squares > header.square_count ||
                squares > header.square_count - page.squares) {
            return R6_ERR_FORMAT;
        }
        squares += page.squares;
    }
    for (at = 0; at < header.function_count; at++) {
        char name[64];
        result = sgr_function(data, size, at, name, sizeof(name));
        if (result != R6_OK) {
            return result;
        }
    }
    if (ids != header.item_count || squares != header.square_count) {
        return R6_ERR_FORMAT;
    }
    r6_memcpy(out, &header, sizeof(header));
    return R6_OK;
}

int r6_sugoroku_category(const void *data, size_t size, uint32_t index,
                         r6_sugoroku_category_t *out) {
    return sgr_category(data, size, index, out);
}

int r6_sugoroku_page(const void *data, size_t size, uint32_t index,
                     r6_sugoroku_page_t *out) {
    return sgr_page(data, size, index, out);
}

int r6_sugoroku_function(const void *data, size_t size, uint32_t index,
                         char *out, size_t capacity) {
    return sgr_function(data, size, index, out, capacity);
}
