/* Bounds-checked access to the packed customization catalog. No CRT/files. */

#include "r6/r6_custom.h"

#include "core/internal.h"

static int custom_layout(const unsigned char *bytes, size_t size,
                         size_t *counts) {
    static const unsigned char magic[8] = {
        'R', '6', 'C', 'U', 'S', 0, 1, 0
    };
    size_t offset;
    size_t i;
    static const size_t sizes[5] = {
        R6_CUSTOM_COLOR_SIZE, R6_CUSTOM_WHEEL_SIZE, R6_CUSTOM_AERO_SIZE,
        R6_CUSTOM_TUNE_SIZE, R6_CUSTOM_TIRE_SIZE
    };

    if (!bytes || !counts) {
        return R6_ERR_ARG;
    }
    if (size < R6_CUSTOM_HEADER_SIZE ||
            r6_memcmp(bytes, magic, sizeof(magic)) != 0) {
        return R6_ERR_FORMAT;
    }
    if (r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    offset = R6_CUSTOM_HEADER_SIZE;
    for (i = 0; i < 5; i++) {
        size_t count = r6_u32(bytes, 12 + (size_t)i * 4);
        if (count > ((size_t)-1 - offset) / sizes[i]) {
            return R6_ERR_FORMAT;
        }
        counts[i] = count;
        offset += count * sizes[i];
    }
    return offset == size ? R6_OK : R6_ERR_FORMAT;
}

int r6_custom_catalog_parse(const void *data, size_t size,
                            r6_custom_catalog *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t counts[5];
    size_t offset;
    size_t i;
    size_t *count_fields[5];
    const unsigned char **pointers[5];
    int rc;

    if (!data || !out) {
        return R6_ERR_ARG;
    }
    rc = custom_layout(bytes, size, counts);
    if (rc != R6_OK) {
        return rc;
    }
    offset = R6_CUSTOM_HEADER_SIZE;
    count_fields[R6_CUSTOM_SECTION_COLOR] = &out->color_count;
    count_fields[R6_CUSTOM_SECTION_WHEEL] = &out->wheel_count;
    count_fields[R6_CUSTOM_SECTION_AERO] = &out->aero_count;
    count_fields[R6_CUSTOM_SECTION_TUNE] = &out->tune_count;
    count_fields[R6_CUSTOM_SECTION_TIRE] = &out->tire_count;
    pointers[R6_CUSTOM_SECTION_COLOR] = (const unsigned char **)&out->colors;
    pointers[R6_CUSTOM_SECTION_WHEEL] = (const unsigned char **)&out->wheels;
    pointers[R6_CUSTOM_SECTION_AERO] = (const unsigned char **)&out->aeros;
    pointers[R6_CUSTOM_SECTION_TUNE] = (const unsigned char **)&out->tunes;
    pointers[R6_CUSTOM_SECTION_TIRE] = (const unsigned char **)&out->tires;
    for (i = 0; i < 5; i++) {
        *pointers[i] = bytes + offset;
        *count_fields[i] = counts[i];
        offset += counts[i] *
                  (i == R6_CUSTOM_SECTION_COLOR ? R6_CUSTOM_COLOR_SIZE :
                   i == R6_CUSTOM_SECTION_WHEEL ? R6_CUSTOM_WHEEL_SIZE :
                   i == R6_CUSTOM_SECTION_AERO ? R6_CUSTOM_AERO_SIZE :
                   i == R6_CUSTOM_SECTION_TUNE ? R6_CUSTOM_TUNE_SIZE :
                                                R6_CUSTOM_TIRE_SIZE);
    }
    return R6_OK;
}

static int custom_at(const void *section, size_t count, size_t index,
                     size_t record_size, void *out) {
    if (!section || !out || index >= count) {
        return R6_ERR_ARG;
    }
    r6_memcpy(out, (const unsigned char *)section + index * record_size,
              record_size);
    return R6_OK;
}

int r6_custom_catalog_color(const r6_custom_catalog *catalog, size_t index,
                            r6_custom_color *out) {
    return catalog ? custom_at(catalog->colors, catalog->color_count, index,
                               R6_CUSTOM_COLOR_SIZE, out) : R6_ERR_ARG;
}

int r6_custom_catalog_wheel(const r6_custom_catalog *catalog, size_t index,
                            r6_custom_wheel *out) {
    return catalog ? custom_at(catalog->wheels, catalog->wheel_count, index,
                               R6_CUSTOM_WHEEL_SIZE, out) : R6_ERR_ARG;
}

int r6_custom_catalog_aero(const r6_custom_catalog *catalog, size_t index,
                           r6_custom_aero *out) {
    return catalog ? custom_at(catalog->aeros, catalog->aero_count, index,
                               R6_CUSTOM_AERO_SIZE, out) : R6_ERR_ARG;
}

int r6_custom_catalog_tune(const r6_custom_catalog *catalog, size_t index,
                           r6_custom_tune *out) {
    return catalog ? custom_at(catalog->tunes, catalog->tune_count, index,
                               R6_CUSTOM_TUNE_SIZE, out) : R6_ERR_ARG;
}

int r6_custom_catalog_tire(const r6_custom_catalog *catalog, size_t index,
                           r6_custom_tire *out) {
    return catalog ? custom_at(catalog->tires, catalog->tire_count, index,
                               R6_CUSTOM_TIRE_SIZE, out) : R6_ERR_ARG;
}

static size_t text_length(const char *text, size_t limit) {
    size_t length = 0;
    while (length < limit && text[length]) {
        length++;
    }
    return length;
}

static int field_equals(const char *field, const char *text, size_t length,
                        size_t limit) {
    size_t i;
    if (length == 0 || length >= limit) {
        return 0;
    }
    for (i = 0; i < length; i++) {
        if (field[i] != text[i]) {
            return 0;
        }
    }
    return field[length] == 0;
}

int r6_custom_catalog_find_color(const r6_custom_catalog *catalog,
                                 uint16_t id) {
    size_t i;
    if (!catalog || !catalog->colors) {
        return -1;
    }
    for (i = 0; i < catalog->color_count; i++) {
        r6_custom_color color;
        if (r6_custom_catalog_color(catalog, i, &color) != R6_OK) {
            return -1;
        }
        if (color.id == id) {
            return (int)i;
        }
    }
    return -1;
}

int r6_custom_catalog_find_wheel(const r6_custom_catalog *catalog,
                                 const char *name) {
    size_t i;
    size_t length;
    if (!catalog || !catalog->wheels || !name) {
        return -1;
    }
    length = text_length(name, R6_CUSTOM_NAME_SIZE);
    if (length == 0 || length == R6_CUSTOM_NAME_SIZE) {
        return -1;
    }
    for (i = 0; i < catalog->wheel_count; i++) {
        r6_custom_wheel wheel;
        if (r6_custom_catalog_wheel(catalog, i, &wheel) != R6_OK) {
            return -1;
        }
        if (field_equals(wheel.name, name, length, R6_CUSTOM_NAME_SIZE)) {
            return (int)i;
        }
    }
    return -1;
}

int r6_custom_catalog_find_aero(const r6_custom_catalog *catalog,
                                const char *name) {
    size_t i;
    size_t length;
    if (!catalog || !catalog->aeros || !name) {
        return -1;
    }
    length = text_length(name, R6_CUSTOM_PART_NAME_SIZE);
    if (length == 0 || length == R6_CUSTOM_PART_NAME_SIZE) {
        return -1;
    }
    for (i = 0; i < catalog->aero_count; i++) {
        r6_custom_aero aero;
        if (r6_custom_catalog_aero(catalog, i, &aero) != R6_OK) {
            return -1;
        }
        if (field_equals(aero.name, name, length,
                         R6_CUSTOM_PART_NAME_SIZE)) {
            return (int)i;
        }
    }
    return -1;
}

int r6_custom_catalog_find_tune(const r6_custom_catalog *catalog,
                                const char *model) {
    size_t i;
    size_t length;
    if (!catalog || !catalog->tunes || !model) {
        return -1;
    }
    length = text_length(model, R6_CUSTOM_NAME_SIZE);
    if (length == 0 || length == R6_CUSTOM_NAME_SIZE) {
        return -1;
    }
    for (i = 0; i < catalog->tune_count; i++) {
        r6_custom_tune tune;
        if (r6_custom_catalog_tune(catalog, i, &tune) != R6_OK) {
            return -1;
        }
        if (field_equals(tune.model, model, length, R6_CUSTOM_NAME_SIZE)) {
            return (int)i;
        }
    }
    return -1;
}
