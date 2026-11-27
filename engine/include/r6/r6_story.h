/* Packed story catalog generated from shipped ESeries scene data and msgdb.
 *
 * The freestanding core only validates a host-owned .r6story blob and returns
 * typed views. Strings live in one shared NUL-terminated section; accessors
 * copy them into caller storage so unaligned buffers stay safe.
 */
#ifndef R6_STORY_H
#define R6_STORY_H

#include <stddef.h>
#include <stdint.h>

#include "r6/r6.h"

#ifdef __cplusplus
extern "C" {
#endif

#define R6_STORY_HEADER_SIZE 32
#define R6_STORY_EPISODE_SIZE 64
#define R6_STORY_MESSAGE_SIZE 16
#define R6_STORY_EVENT_SIZE 32
#define R6_STORY_KEY_SIZE 16

enum r6_story_phase {
    R6_STORY_FRONT = 1,
    R6_STORY_RACE = 2,
    R6_STORY_REAR = 3
};

enum r6_story_episode_flags {
    R6_STORY_EP_FRONT = 1,
    R6_STORY_EP_RACE = 2,
    R6_STORY_EP_REAR = 4,
    R6_STORY_EP_BRANCH_B = 8,
    R6_STORY_EP_ENDING = 16,
    R6_STORY_EP_ENVIRONMENT = 32
};

enum r6_story_event_kind {
    R6_STORY_EVENT_MESSAGE = 1,
    R6_STORY_EVENT_LETTERING = 2,
    R6_STORY_EVENT_CUTIN_HIT = 3,
    R6_STORY_EVENT_CUTIN_RANGE = 4
};

typedef struct r6_story_episode {
    uint32_t enum_index;      /* index in the ESeries_* name table */
    char name[32];            /* directory name, e.g. ESeries_009B */
    uint32_t flags;           /* r6_story_episode_flags */
    uint16_t message_count;
    uint16_t event_count;
    uint16_t actors[4];       /* raw ACTOR_* numbers, mapping unresolved */
    uint16_t stage;           /* raw STAGE number, mapping unresolved */
    uint8_t stage_root;
    uint8_t stage_day;
    uint8_t cam_id;
    uint8_t pad[7];
} r6_story_episode;

typedef struct r6_story_message {
    uint32_t text_offset;
    uint16_t episode;
    uint16_t local_id;        /* index in the paired Message.xmlt */
    uint16_t text_len;
    uint8_t phase;
    uint8_t pad[5];
} r6_story_message;

typedef struct r6_story_event {
    uint16_t episode;
    uint8_t phase;
    uint8_t kind;             /* r6_story_event_kind */
    int32_t start_frame;
    int32_t end_frame;
    uint32_t range;           /* CUT_IN_RANGE source units */
    uint16_t mes_id;
    uint8_t actor;            /* CAR_ID slot for CUT_IN_HIT */
    uint8_t pos;
    uint32_t text_offset;     /* FACE_NAME / FILE_NAME / TEX_NAME_0 */
    uint16_t text_len;
    uint8_t pad[6];
} r6_story_event;

typedef struct r6_story_key {
    uint32_t id_offset;
    uint32_t value_offset;
    uint16_t id_len;
    uint16_t value_len;
    uint8_t pad[4];
} r6_story_key;

typedef struct r6_story_catalog {
    const r6_story_episode *episodes;
    const r6_story_message *messages;
    const r6_story_event *events;
    const r6_story_key *keys;
    const char *strings;
    size_t episode_count;
    size_t message_count;
    size_t event_count;
    size_t key_count;
    size_t string_count;
} r6_story_catalog;

/* Direct counts of stored raw fields; no dialogue or unlock semantics. */
typedef struct r6_story_summary_t {
    uint32_t message_phase[3];   /* FRONT, RACE, REAR */
    uint32_t event_phase[3];
    uint32_t event_kind[4];      /* MESSAGE, LETTERING, CUTIN_HIT, CUTIN_RANGE */
    uint32_t branch_b;
    uint32_t ending;
    uint32_t environment;
    uint32_t enum_zero;
    uint32_t empty_key_values;
} r6_story_summary_t;

R6_API int r6_story_catalog_parse(const void *data, size_t size,
                                  r6_story_catalog *out);
R6_API int r6_story_catalog_summary(const r6_story_catalog *catalog,
                                    r6_story_summary_t *out);
R6_API int r6_story_catalog_episode(const r6_story_catalog *catalog,
                                    size_t index, r6_story_episode *out);
R6_API int r6_story_catalog_message(const r6_story_catalog *catalog,
                                    size_t index, r6_story_message *out);
R6_API int r6_story_catalog_event(const r6_story_catalog *catalog,
                                  size_t index, r6_story_event *out);
R6_API int r6_story_catalog_key(const r6_story_catalog *catalog,
                                size_t index, r6_story_key *out);
R6_API int r6_story_catalog_message_text(const r6_story_catalog *catalog,
                                         size_t index, char *out, size_t cap);
R6_API int r6_story_catalog_event_text(const r6_story_catalog *catalog,
                                       size_t index, char *out, size_t cap);
R6_API int r6_story_catalog_key_id(const r6_story_catalog *catalog,
                                   size_t index, char *out, size_t cap);
R6_API int r6_story_catalog_key_value(const r6_story_catalog *catalog,
                                      size_t index, char *out, size_t cap);
R6_API int r6_story_catalog_find_episode(const r6_story_catalog *catalog,
                                         const char *name);
R6_API int r6_story_catalog_find_key(const r6_story_catalog *catalog,
                                     const char *key);

#ifdef __cplusplus
}
#endif

#endif
