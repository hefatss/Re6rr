/* Bounds-checked unpacking of the packed car catalog. No CRT and no files. */

#include "r6/r6_car.h"

#include "core/internal.h"

static int catalog_layout(const unsigned char *bytes, size_t size,
                          size_t *car_count, size_t *map_count) {
    static const unsigned char magic[8] = {
        'R', '6', 'C', 'A', 'R', 0, 1, 0
    };
    uint32_t version;
    uint32_t car_count_value;
    uint32_t map_count_value;
    uint32_t record_size;
    size_t car_bytes;
    size_t required;

    if (!bytes || !car_count || !map_count) {
        return R6_ERR_ARG;
    }
    if (size < R6_CAR_HEADER_SIZE) {
        return R6_ERR_FORMAT;
    }
    if (r6_memcmp(bytes, magic, sizeof(magic)) != 0) {
        return R6_ERR_FORMAT;
    }
    version = r6_u32(bytes, 8);
    if (version != 1u && version != 2u) {
        return R6_ERR_FORMAT;
    }
    car_count_value = r6_u32(bytes, 12);
    record_size = r6_u32(bytes, 16);
    map_count_value = r6_u32(bytes, 20);
    if (record_size != R6_CAR_RECORD_SIZE ||
            (version == 1u && map_count_value != 0u)) {
        return R6_ERR_FORMAT;
    }
    if ((size_t)car_count_value > ((size_t)-1 - R6_CAR_HEADER_SIZE) /
            R6_CAR_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    car_bytes = (size_t)car_count_value * R6_CAR_RECORD_SIZE;
    if ((size_t)map_count_value >
            ((size_t)-1 - R6_CAR_HEADER_SIZE - car_bytes) /
            R6_CAR_MAP_SIZE) {
        return R6_ERR_FORMAT;
    }
    required = R6_CAR_HEADER_SIZE + car_bytes +
               (size_t)map_count_value * R6_CAR_MAP_SIZE;
    if (size != required) {
        return R6_ERR_FORMAT;
    }
    *car_count = car_count_value;
    *map_count = map_count_value;
    return R6_OK;
}

static size_t text_length(const char *text, size_t limit) {
    size_t length = 0;
    while (length < limit && text[length]) {
        length++;
    }
    return length;
}

static size_t field_length(const unsigned char *field, size_t limit) {
    size_t length = 0;
    while (length < limit && field[length]) {
        length++;
    }
    return length;
}

static int field_equals(const unsigned char *field, const char *text,
                        size_t length, size_t limit) {
    size_t i;
    if (length == 0 || length >= limit) {
        return 0;
    }
    for (i = 0; i < length; i++) {
        if (field[i] != (unsigned char)text[i]) {
            return 0;
        }
    }
    return field[length] == 0;
}

int r6_car_catalog_parse(const void *data, size_t size,
                         r6_car_info *cars, size_t capacity, size_t *count) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t car_count = 0;
    size_t map_count = 0;
    size_t i;
    int rc;

    if (!data || !count) {
        return R6_ERR_ARG;
    }
    rc = catalog_layout(bytes, size, &car_count, &map_count);
    if (rc != R6_OK) {
        return rc;
    }
    if (!cars || car_count > capacity) {
        *count = car_count;
        return R6_ERR_BUFFER;
    }
    for (i = 0; i < car_count; i++) {
        r6_memcpy(&cars[i], bytes + R6_CAR_HEADER_SIZE +
                  i * R6_CAR_RECORD_SIZE, R6_CAR_RECORD_SIZE);
    }
    *count = car_count;
    return R6_OK;
}

int r6_car_catalog_find_model(const r6_car_info *cars, size_t count,
                              const char *model) {
    size_t i;
    size_t length;
    if (!cars || !model) {
        return -1;
    }
    length = text_length(model, R6_CAR_MODEL_SIZE);
    if (length == 0 || length == R6_CAR_MODEL_SIZE) {
        return -1;
    }
    for (i = 0; i < count; i++) {
        if (field_equals((const unsigned char *)cars[i].model, model, length,
                         R6_CAR_MODEL_SIZE)) {
            return (int)i;
        }
    }
    return -1;
}

int r6_car_catalog_find_id(const r6_car_info *cars, size_t count,
                           uint16_t model_id) {
    size_t i;
    if (!cars) {
        return -1;
    }
    for (i = 0; i < count; i++) {
        if (cars[i].model_id == model_id) {
            return (int)i;
        }
    }
    return -1;
}

int r6_car_catalog_character_count(const void *data, size_t size) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t car_count = 0;
    size_t map_count = 0;
    if (catalog_layout(bytes, size, &car_count, &map_count) != R6_OK ||
            map_count > 0x7fffffffu) {
        return -1;
    }
    return (int)map_count;
}

int r6_car_catalog_find_character(const void *data, size_t size,
                                  const char *character) {
    const unsigned char *bytes = (const unsigned char *)data;
    const unsigned char *maps;
    const unsigned char *cars;
    size_t car_count = 0;
    size_t map_count = 0;
    size_t length;
    size_t i;
    size_t j;

    if (!data || !character ||
            catalog_layout(bytes, size, &car_count, &map_count) != R6_OK) {
        return -1;
    }
    length = text_length(character, R6_CAR_MODEL_SIZE);
    if (length == 0 || length == R6_CAR_MODEL_SIZE) {
        return -1;
    }
    cars = bytes + R6_CAR_HEADER_SIZE;
    maps = cars + car_count * R6_CAR_RECORD_SIZE;
    for (i = 0; i < map_count; i++) {
        const unsigned char *entry = maps + i * R6_CAR_MAP_SIZE;
        const unsigned char *model = entry + R6_CAR_MODEL_SIZE;
        size_t model_length;
        if (!field_equals(entry, character, length, R6_CAR_MODEL_SIZE)) {
            continue;
        }
        model_length = field_length(model, R6_CAR_MODEL_SIZE);
        if (model_length == 0 || model_length == R6_CAR_MODEL_SIZE) {
            continue;
        }
        for (j = 0; j < car_count; j++) {
            if (field_equals(cars + j * R6_CAR_RECORD_SIZE,
                             (const char *)model, model_length,
                             R6_CAR_MODEL_SIZE)) {
                return (int)j;
            }
        }
    }
    return -1;
}
