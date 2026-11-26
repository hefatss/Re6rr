/* Stateless polyline projection. No CRT, no libm, no host calls. */

#include "r6/r6_course.h"

#include "core/internal.h"

#define R6_COURSE_EPSILON 1e-6f

static float course_abs(float value) {
    return value < 0.0f ? -value : value;
}

static float course_sqrt(float value) {
    float guess;
    int i;
    if (value <= 0.0f) {
        return 0.0f;
    }
    {
        unsigned int bits;
        r6_memcpy(&bits, &value, sizeof(bits));
        bits = (bits >> 1) + 0x1fc00000u;
        r6_memcpy(&guess, &bits, sizeof(guess));
    }
    for (i = 0; i < 3; i++) {
        guess = 0.5f * (guess + value / guess);
    }
    return guess;
}

static int course_segment(const r6_course_vertex *vertices, size_t count,
                          int closed, size_t index,
                          const r6_course_vertex **a,
                          const r6_course_vertex **b) {
    if (index >= count || !vertices) {
        return R6_ERR_ARG;
    }
    *a = &vertices[index];
    if (index + 1 < count) {
        *b = &vertices[index + 1];
    } else if (closed) {
        *b = &vertices[0];
    } else {
        return 0;
    }
    return 1;
}

int r6_course_length(const r6_course_vertex *vertices, size_t count,
                     int closed, float *out_length) {
    size_t i;
    size_t segments;
    float length = 0.0f;

    if (!vertices || count < 2 || !out_length) {
        return R6_ERR_ARG;
    }
    segments = closed ? count : count - 1;
    for (i = 0; i < segments; i++) {
        const r6_course_vertex *a;
        const r6_course_vertex *b;
        float dx;
        float dz;
        int rc = course_segment(vertices, count, closed, i, &a, &b);
        if (rc != 1) {
            return R6_ERR_ARG;
        }
        dx = b->x - a->x;
        dz = b->z - a->z;
        length += course_sqrt(dx * dx + dz * dz);
    }
    *out_length = length;
    return R6_OK;
}

int r6_course_project(const r6_course_vertex *vertices, size_t count,
                      int closed, float x, float z,
                      r6_course_projection *out) {
    size_t i;
    size_t segments;
    size_t best_segment = 0;
    float best_d2 = 0.0f;
    float best_t = 0.0f;
    float travelled = 0.0f;
    float total = 0.0f;
    int have_best = 0;

    if (!vertices || count < 2 || !out) {
        return R6_ERR_ARG;
    }
    segments = closed ? count : count - 1;
    if (r6_course_length(vertices, count, closed, &total) != R6_OK) {
        return R6_ERR_ARG;
    }

    for (i = 0; i < segments; i++) {
        const r6_course_vertex *a;
        const r6_course_vertex *b;
        float dx;
        float dz;
        float len2;
        float t;
        float px;
        float pz;
        float ox;
        float oz;
        float d2;
        if (course_segment(vertices, count, closed, i, &a, &b) != 1) {
            return R6_ERR_ARG;
        }
        dx = b->x - a->x;
        dz = b->z - a->z;
        len2 = dx * dx + dz * dz;
        t = 0.0f;
        if (len2 > R6_COURSE_EPSILON) {
            t = ((x - a->x) * dx + (z - a->z) * dz) / len2;
        }
        if (t < 0.0f) {
            t = 0.0f;
        } else if (t > 1.0f) {
            t = 1.0f;
        }
        px = a->x + t * dx;
        pz = a->z + t * dz;
        ox = x - px;
        oz = z - pz;
        d2 = ox * ox + oz * oz;
        if (!have_best || d2 < best_d2) {
            have_best = 1;
            best_d2 = d2;
            best_t = t;
            best_segment = i;
        }
        travelled += course_sqrt(len2);
    }
    if (!have_best) {
        return R6_ERR_FORMAT;
    }

    /* Recompute the arc length up to the winning segment. */
    travelled = 0.0f;
    for (i = 0; i < best_segment; i++) {
        const r6_course_vertex *a;
        const r6_course_vertex *b;
        float dx = 0.0f;
        float dz = 0.0f;
        if (course_segment(vertices, count, closed, i, &a, &b) == 1) {
            dx = b->x - a->x;
            dz = b->z - a->z;
            travelled += course_sqrt(dx * dx + dz * dz);
        }
    }

    {
        const r6_course_vertex *a;
        const r6_course_vertex *b;
        const r6_course_vertex *nearer;
        float dx;
        float dz;
        float len;
        float ox;
        float oz;
        r6_memset(out, 0, sizeof(*out));
        if (course_segment(vertices, count, closed, best_segment,
                           &a, &b) != 1) {
            return R6_ERR_ARG;
        }
        dx = b->x - a->x;
        dz = b->z - a->z;
        len = course_sqrt(dx * dx + dz * dz);
        if (len <= R6_COURSE_EPSILON) {
            len = 1.0f;
            dx = 1.0f;
            dz = 0.0f;
        }
        out->tangent_x = dx / len;
        out->tangent_z = dz / len;
        ox = x - (a->x + best_t * dx);
        oz = z - (a->z + best_t * dz);
        out->lateral = ox * -out->tangent_z + oz * out->tangent_x;
        out->distance = travelled + best_t * len;
        if (closed) {
            if (out->distance >= total) {
                out->distance -= total;
            }
        } else if (out->distance > total) {
            out->distance = total;
        }
        out->height = a->y + best_t * (b->y - a->y);
        out->half_width = a->half_width +
                          best_t * (b->half_width - a->half_width);
        nearer = best_t < 0.5f ? a : b;
        out->surface = nearer->surface;
        out->flags = nearer->flags;
        out->segment = best_segment;
    }
    return R6_OK;
}

int r6_course_at(const r6_course_vertex *vertices, size_t count,
                 int closed, float distance, float out[3]) {
    size_t i;
    size_t segments;
    float total = 0.0f;
    float target;

    if (!vertices || count < 2 || !out) {
        return R6_ERR_ARG;
    }
    if (r6_course_length(vertices, count, closed, &total) != R6_OK ||
        total <= 0.0f) {
        return R6_ERR_ARG;
    }
    target = distance;
    while (target < 0.0f) {
        target += total;
    }
    while (target > total) {
        target -= total;
    }
    segments = closed ? count : count - 1;
    for (i = 0; i < segments; i++) {
        const r6_course_vertex *a;
        const r6_course_vertex *b;
        float dx;
        float dz;
        float len;
        if (course_segment(vertices, count, closed, i, &a, &b) != 1) {
            return R6_ERR_ARG;
        }
        dx = b->x - a->x;
        dz = b->z - a->z;
        len = course_sqrt(dx * dx + dz * dz);
        if (target <= len || i + 1 == segments) {
            float t = len > R6_COURSE_EPSILON ? target / len : 0.0f;
            out[0] = a->x + t * dx;
            out[1] = a->y + t * (b->y - a->y);
            out[2] = a->z + t * dz;
            return R6_OK;
        }
        target -= len;
    }
    return R6_ERR_FORMAT;
}

int r6_course_descriptor_parse(const void *data, size_t size,
                               uint32_t *flags, r6_course_vertex *vertices,
                               size_t capacity, size_t *count) {
    static const unsigned char magic[8] = {
        'R', '6', 'C', 'R', 'S', 0, 1, 0
    };
    const unsigned char *bytes = (const unsigned char *)data;
    uint32_t version;
    uint32_t vertex_count;
    size_t i;
    size_t required;

    if (!data || !flags || !count) {
        return R6_ERR_ARG;
    }
    if (size < 24) {
        return R6_ERR_FORMAT;
    }
    if (r6_memcmp(bytes, magic, sizeof(magic)) != 0) {
        return R6_ERR_FORMAT;
    }
    version = r6_u32(bytes, 8);
    if (version != 1u) {
        return R6_ERR_FORMAT;
    }
    *flags = r6_u32(bytes, 12);
    vertex_count = r6_u32(bytes, 16);
    required = 24u + (size_t)vertex_count * 20u;
    if (size != required) {
        return R6_ERR_FORMAT;
    }
    if (vertex_count > capacity || !vertices) {
        *count = vertex_count;
        return R6_ERR_BUFFER;
    }
    for (i = 0; i < vertex_count; i++) {
        size_t at = 24u + i * 20u;
        r6_course_vertex *out = &vertices[i];
        r6_memcpy(&out->x, bytes + at, 4);
        r6_memcpy(&out->y, bytes + at + 4, 4);
        r6_memcpy(&out->z, bytes + at + 8, 4);
        r6_memcpy(&out->half_width, bytes + at + 12, 4);
        out->surface = bytes[at + 16];
        out->flags = bytes[at + 17];
        out->reserved = r6_u16(bytes, at + 18);
    }
    *count = vertex_count;
    return R6_OK;
}

static char course_lower(char value) {
    return value >= 'A' && value <= 'Z' ? (char)(value - 'A' + 'a') : value;
}

static int course_contains_ci(const char *text, size_t length,
                              const char *needle) {
    size_t wide = r6_strlen(needle);
    size_t index;
    if (!wide || wide > length) {
        return 0;
    }
    for (index = 0; index + wide <= length; index++) {
        size_t offset;
        for (offset = 0; offset < wide; offset++) {
            if (course_lower(text[index + offset]) != needle[offset]) {
                break;
            }
        }
        if (offset == wide) {
            return 1;
        }
    }
    return 0;
}

static int course_has_any(const char *text, size_t length,
                          const char *const *tokens, size_t count) {
    size_t index;
    for (index = 0; index < count; index++) {
        if (course_contains_ci(text, length, tokens[index])) {
            return 1;
        }
    }
    return 0;
}

int r6_course_classify_surface(const char *name) {
    static const char *const gravel[] = {"gravel", "grail", "dirt", "sand"};
    static const char *const grass[] = {"grass", "kusa", "green", "bush",
                                        "weed"};
    static const char *const road[] = {"broad", "nroad", "route", "road",
                                       "conc", "asph", "pavement", "futa",
                                       "tunnel"};
    size_t length;
    size_t suffix = 0;
    size_t index;
    if (!name) {
        return R6_SURFACE_UNKNOWN;
    }
    length = r6_strlen(name);
    for (index = 0; index + 5 <= length; index++) {
        if (r6_memcmp(name + index, "PICE_", 5) == 0) {
            suffix = index + 5;
        }
    }
    name += suffix;
    length -= suffix;
    if (course_has_any(name, length, gravel, 4)) {
        return R6_SURFACE_GRAVEL;
    }
    if (course_has_any(name, length, grass, 5)) {
        return R6_SURFACE_GRASS;
    }
    if (course_has_any(name, length, road, 9)) {
        return R6_SURFACE_ROAD;
    }
    return R6_SURFACE_UNKNOWN;
}
