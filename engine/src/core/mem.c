#include "internal.h"

void *r6_memcpy(void *dst, const void *src, size_t size) {
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    size_t i;
    for (i = 0; i < size; i++) {
        d[i] = s[i];
    }
    return dst;
}

void *r6_memset(void *dst, int value, size_t size) {
    unsigned char *d = (unsigned char *)dst;
    size_t i;
    for (i = 0; i < size; i++) {
        d[i] = (unsigned char)value;
    }
    return dst;
}

int r6_memcmp(const void *a, const void *b, size_t size) {
    const unsigned char *x = (const unsigned char *)a;
    const unsigned char *y = (const unsigned char *)b;
    size_t i;
    for (i = 0; i < size; i++) {
        if (x[i] != y[i]) {
            return (int)x[i] - (int)y[i];
        }
    }
    return 0;
}

size_t r6_strlen(const char *text) {
    size_t n = 0;
    if (!text) {
        return 0;
    }
    while (text[n]) {
        n++;
    }
    return n;
}

void r6_arena_init(r6_arena *arena, void *base, size_t capacity) {
    arena->base = (unsigned char *)base;
    arena->capacity = base ? capacity : 0;
    arena->used = 0;
}

void r6_arena_reset(r6_arena *arena) {
    arena->used = 0;
}

void *r6_arena_alloc(r6_arena *arena, size_t size, size_t align) {
    size_t start;
    if (!arena || !arena->base || size == 0) {
        return 0;
    }
    if (align < 1) {
        align = 1;
    }
    start = (arena->used + align - 1) / align * align;
    if (start < arena->used || start > arena->capacity ||
        size > arena->capacity - start) {
        return 0;
    }
    arena->used = start + size;
    return arena->base + start;
}
