/* Bounds-checked unpacking of the packed car catalog. No CRT and no files. */

#include "r6/r6_car.h"

#include "core/internal.h"

int r6_car_catalog_parse(const void *data, size_t size,
                         r6_car_info *cars, size_t capacity, size_t *count) {
    static const unsigned char magic[8] = {
        'R', '6', 'C', 'A', 'R', 0, 1, 0
    };
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t version;
    uint32_t count_value;
    uint32_t record_size;
    size_t i;
    size_t required;

    if (!data || !count) {
        return R6_ERR_ARG;
    }
    if (size < R6_CAR_HEADER_SIZE) {
        return R6_ERR_FORMAT;
    }
    if (r6_memcmp(bytes, magic, sizeof(magic)) != 0) {
        return R6_ERR_FORMAT;
    }
    version = r6_u32(bytes, 8);
    if (version != 1u) {
        return R6_ERR_FORMAT;
    }
    count_value = r6_u32(bytes, 12);
    record_size = r6_u32(bytes, 16);
    if (record_size != R6_CAR_RECORD_SIZE) {
        return R6_ERR_FORMAT;
    }
    required = R6_CAR_HEADER_SIZE + (size_t)count_value *
               R6_CAR_RECORD_SIZE;
    if (size != required) {
        return R6_ERR_FORMAT;
    }
    if (!cars || count_value > capacity) {
        *count = count_value;
        return R6_ERR_BUFFER;
    }
    for (i = 0; i < count_value; i++) {
        const unsigned char *at = bytes + R6_CAR_HEADER_SIZE +
                                  i * R6_CAR_RECORD_SIZE;
        r6_car_info *out = &cars[i];
        r6_memcpy(out, at, R6_CAR_RECORD_SIZE);
    }
    *count = count_value;
    return R6_OK;
}

int r6_car_catalog_find_model(const r6_car_info *cars, size_t count,
                              const char *model) {
    size_t i;
    size_t length;
    if (!cars || !model) {
        return -1;
    }
    length = 0;
    while (model[length] && length < R6_CAR_MODEL_SIZE) {
        length++;
    }
    if (length == 0 || length == R6_CAR_MODEL_SIZE) {
        return -1;
    }
    for (i = 0; i < count; i++) {
        if (r6_memcmp(cars[i].model, model, length) == 0 &&
            cars[i].model[length] == 0) {
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
