#ifndef R6_INTERNAL_H
#define R6_INTERNAL_H

#include <stddef.h>
#include <stdint.h>

#include "lua.h"
#include "r6/r6.h"

#define R6_ERROR_CAP 256

typedef struct r6_arena {
    unsigned char *base;
    size_t capacity;
    size_t used;
} r6_arena;

void r6_arena_init(r6_arena *arena, void *base, size_t capacity);
void *r6_arena_alloc(r6_arena *arena, size_t size, size_t align);
void r6_arena_reset(r6_arena *arena);

void *r6_memcpy(void *dst, const void *src, size_t size);
void *r6_memset(void *dst, int value, size_t size);
int r6_memcmp(const void *a, const void *b, size_t size);
size_t r6_strlen(const char *text);

typedef struct r6_engine {
    lua_State *L;
    r6_arena arena;
    r6_log_fn log;
    void *log_user;
    char error[R6_ERROR_CAP];
} r6_engine;

void r6_set_error(r6_engine *engine, const char *message);
void r6_log(r6_engine *engine, int level, const char *message);

static inline uint16_t r6_u16(const void *data, size_t offset) {
    const unsigned char *p = (const unsigned char *)data + offset;
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static inline uint32_t r6_u32(const void *data, size_t offset) {
    const unsigned char *p = (const unsigned char *)data + offset;
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline int r6_match(const void *data, size_t size, size_t at,
                           const char *tag, size_t tag_len) {
    return at + tag_len <= size &&
           r6_memcmp((const unsigned char *)data + at, tag, tag_len) == 0;
}

#endif
