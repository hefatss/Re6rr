/* Road/course projection for the freestanding core.
 *
 * Geometry is supplied by the host as an ordered polyline. The core copies
 * nothing and computes arc length on demand, so the same code works with a
 * Python-generated descriptor on the host and a compressed descriptor on
 * Android. Units are metres; x/z are the ground plane, y is height.
 */
#ifndef R6_COURSE_H
#define R6_COURSE_H

#include <stddef.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Surface class inferred from shipped LOADLIST ROAD_NAME labels. -1 means the
 * label does not carry a recognized surface token. */
enum r6_course_surface {
    R6_SURFACE_UNKNOWN = -1,
    R6_SURFACE_ROAD = 0,
    R6_SURFACE_GRASS = 1,
    R6_SURFACE_GRAVEL = 2
};

R6_API int r6_course_classify_surface(const char *name);

enum r6_course_flags {
    R6_COURSE_CHECKPOINT = 1u,
    R6_COURSE_START = 2u,
    R6_COURSE_GOAL = 4u,
    R6_COURSE_JUNCTION = 8u
};

typedef struct r6_course_vertex {
    float x, y, z;
    float half_width;   /* metres, drivable half-width */
    uint8_t surface;    /* 0 road, 1 grass, 2 gravel (ESurface-like) */
    uint8_t flags;
    uint16_t reserved;
} r6_course_vertex;

typedef struct r6_course_projection {
    float distance;     /* arc length from vertex 0, metres */
    float lateral;      /* signed offset from centreline, metres */
    float tangent_x, tangent_z;
    float height;
    float half_width;
    uint8_t surface;
    uint8_t flags;
    size_t segment;     /* nearest segment index */
} r6_course_projection;

/* Total arc length of the polyline. closed=1 adds the last->first segment. */
R6_API int r6_course_length(const r6_course_vertex *vertices, size_t count,
                            int closed, float *out_length);

/* Nearest point on the polyline to (x,z). Count must be at least two. */
R6_API int r6_course_project(const r6_course_vertex *vertices, size_t count,
                             int closed, float x, float z,
                             r6_course_projection *out);

/* Interpolate a centreline point at a given arc length. */
R6_API int r6_course_at(const r6_course_vertex *vertices, size_t count,
                        int closed, float distance, float out[3]);

/* Packed descriptor: 8-byte magic "R6CRS\0\1\0\0", u32 version, u32 flags
 * (bit 0 = closed), u32 count, u32 reserved, then count * 20-byte vertices.
 * On R6_ERR_BUFFER, *count holds the required vertex capacity. */
R6_API int r6_course_descriptor_parse(const void *data, size_t size,
                                      uint32_t *flags,
                                      r6_course_vertex *vertices,
                                      size_t capacity, size_t *count);

#ifdef __cplusplus
}
#endif

#endif
