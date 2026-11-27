/* Bounds-checked access to the packed story catalog. No CRT, files or alloc. */

#include "r6/r6_story.h"

#include "core/internal.h"

static int story_layout(const unsigned char *bytes, size_t size,
                        size_t *counts) {
    static const unsigned char magic[8] = {
        'R', '6', 'S', 'T', 'O', 0, 1, 0
    };
    static const size_t sizes[5] = {
        R6_STORY_EPISODE_SIZE, R6_STORY_MESSAGE_SIZE, R6_STORY_EVENT_SIZE,
        R6_STORY_KEY_SIZE, 1
    };
    size_t offset;
    size_t i;

    if (!bytes || !counts) {
        return R6_ERR_ARG;
    }
    if (size < R6_STORY_HEADER_SIZE ||
            r6_memcmp(bytes, magic, sizeof(magic)) != 0 ||
            r6_u32(bytes, 8) != 1u) {
        return R6_ERR_FORMAT;
    }
    offset = R6_STORY_HEADER_SIZE;
    for (i = 0; i < 5; i++) {
        size_t count = r6_u32(bytes, 12 + i * 4);
        if (count > ((size_t)-1 - offset) / sizes[i]) {
            return R6_ERR_FORMAT;
        }
        counts[i] = count;
        offset += count * sizes[i];
    }
    return offset == size ? R6_OK : R6_ERR_FORMAT;
}

int r6_story_catalog_parse(const void *data, size_t size,
                           r6_story_catalog *out) {
    const unsigned char *bytes = (const unsigned char *)data;
    size_t counts[5];
    size_t offset;
    size_t i;
    size_t *count_fields[5];
    const unsigned char **pointers[5];
    static const size_t sizes[5] = {
        R6_STORY_EPISODE_SIZE, R6_STORY_MESSAGE_SIZE, R6_STORY_EVENT_SIZE,
        R6_STORY_KEY_SIZE, 1
    };
    int rc;

    if (!data || !out) {
        return R6_ERR_ARG;
    }
    rc = story_layout(bytes, size, counts);
    if (rc != R6_OK) {
        return rc;
    }
    count_fields[0] = &out->episode_count;
    count_fields[1] = &out->message_count;
    count_fields[2] = &out->event_count;
    count_fields[3] = &out->key_count;
    count_fields[4] = &out->string_count;
    pointers[0] = (const unsigned char **)&out->episodes;
    pointers[1] = (const unsigned char **)&out->messages;
    pointers[2] = (const unsigned char **)&out->events;
    pointers[3] = (const unsigned char **)&out->keys;
    pointers[4] = (const unsigned char **)&out->strings;
    offset = R6_STORY_HEADER_SIZE;
    for (i = 0; i < 5; i++) {
        *pointers[i] = bytes + offset;
        *count_fields[i] = counts[i];
        offset += counts[i] * sizes[i];
    }
    return R6_OK;
}

int r6_story_catalog_summary(const r6_story_catalog *catalog,
                             r6_story_summary_t *out) {
    r6_story_summary_t summary;
    size_t index;
    if (!catalog || !out) {
        return R6_ERR_ARG;
    }
    r6_memset(&summary, 0, sizeof(summary));
    for (index = 0; index < catalog->episode_count; index++) {
        const unsigned char *row = (const unsigned char *)catalog->episodes +
                                   index * R6_STORY_EPISODE_SIZE;
        uint32_t flags = r6_u32(row, 36);
        if (r6_u32(row, 0) == 0u) {
            summary.enum_zero++;
        }
        if (flags & R6_STORY_EP_BRANCH_B) {
            summary.branch_b++;
        }
        if (flags & R6_STORY_EP_ENDING) {
            summary.ending++;
        }
        if (flags & R6_STORY_EP_ENVIRONMENT) {
            summary.environment++;
        }
    }
    for (index = 0; index < catalog->message_count; index++) {
        const unsigned char *row = (const unsigned char *)catalog->messages +
                                   index * R6_STORY_MESSAGE_SIZE;
        uint8_t phase = row[10];
        if (phase >= 1u && phase <= 3u) {
            summary.message_phase[phase - 1u]++;
        }
    }
    for (index = 0; index < catalog->event_count; index++) {
        const unsigned char *row = (const unsigned char *)catalog->events +
                                   index * R6_STORY_EVENT_SIZE;
        uint8_t phase = row[2];
        uint8_t kind = row[3];
        if (phase >= 1u && phase <= 3u) {
            summary.event_phase[phase - 1u]++;
        }
        if (kind >= 1u && kind <= 4u) {
            summary.event_kind[kind - 1u]++;
        }
    }
    for (index = 0; index < catalog->key_count; index++) {
        const unsigned char *row = (const unsigned char *)catalog->keys +
                                   index * R6_STORY_KEY_SIZE;
        if (r6_u16(row, 10) == 0u) {
            summary.empty_key_values++;
        }
    }
    *out = summary;
    return R6_OK;
}

static int story_at(const void *section, size_t count, size_t index,
                    size_t record_size, void *out) {
    if (!section || !out || index >= count) {
        return R6_ERR_ARG;
    }
    r6_memcpy(out, (const unsigned char *)section + index * record_size,
              record_size);
    return R6_OK;
}

int r6_story_catalog_episode(const r6_story_catalog *catalog, size_t index,
                             r6_story_episode *out) {
    return catalog ? story_at(catalog->episodes, catalog->episode_count, index,
                              R6_STORY_EPISODE_SIZE, out) : R6_ERR_ARG;
}

int r6_story_catalog_message(const r6_story_catalog *catalog, size_t index,
                             r6_story_message *out) {
    return catalog ? story_at(catalog->messages, catalog->message_count, index,
                              R6_STORY_MESSAGE_SIZE, out) : R6_ERR_ARG;
}

int r6_story_catalog_event(const r6_story_catalog *catalog, size_t index,
                           r6_story_event *out) {
    return catalog ? story_at(catalog->events, catalog->event_count, index,
                              R6_STORY_EVENT_SIZE, out) : R6_ERR_ARG;
}

int r6_story_catalog_key(const r6_story_catalog *catalog, size_t index,
                         r6_story_key *out) {
    return catalog ? story_at(catalog->keys, catalog->key_count, index,
                              R6_STORY_KEY_SIZE, out) : R6_ERR_ARG;
}

static int story_string(const r6_story_catalog *catalog, uint32_t offset,
                        uint16_t length, char *out, size_t cap) {
    if (!catalog || !catalog->strings || !out) {
        return R6_ERR_ARG;
    }
    if (offset > catalog->string_count ||
            length > catalog->string_count - offset || cap <= length) {
        return R6_ERR_BUFFER;
    }
    r6_memcpy(out, catalog->strings + offset, length);
    out[length] = 0;
    return R6_OK;
}

int r6_story_catalog_message_text(const r6_story_catalog *catalog,
                                  size_t index, char *out, size_t cap) {
    r6_story_message message;
    int rc = r6_story_catalog_message(catalog, index, &message);
    if (rc != R6_OK) {
        return rc;
    }
    return story_string(catalog, message.text_offset, message.text_len,
                        out, cap);
}

int r6_story_catalog_event_text(const r6_story_catalog *catalog,
                                size_t index, char *out, size_t cap) {
    r6_story_event event;
    int rc = r6_story_catalog_event(catalog, index, &event);
    if (rc != R6_OK) {
        return rc;
    }
    return story_string(catalog, event.text_offset, event.text_len, out, cap);
}

int r6_story_catalog_key_id(const r6_story_catalog *catalog, size_t index,
                            char *out, size_t cap) {
    r6_story_key key;
    int rc = r6_story_catalog_key(catalog, index, &key);
    if (rc != R6_OK) {
        return rc;
    }
    return story_string(catalog, key.id_offset, key.id_len, out, cap);
}

int r6_story_catalog_key_value(const r6_story_catalog *catalog, size_t index,
                               char *out, size_t cap) {
    r6_story_key key;
    int rc = r6_story_catalog_key(catalog, index, &key);
    if (rc != R6_OK) {
        return rc;
    }
    return story_string(catalog, key.value_offset, key.value_len, out, cap);
}

int r6_story_catalog_find_episode(const r6_story_catalog *catalog,
                                  const char *name) {
    size_t i;
    size_t length;
    if (!catalog || !catalog->episodes || !name) {
        return -1;
    }
    length = r6_strlen(name);
    if (!length || length >= 32) {
        return -1;
    }
    for (i = 0; i < catalog->episode_count; i++) {
        r6_story_episode episode;
        if (r6_story_catalog_episode(catalog, i, &episode) != R6_OK) {
            return -1;
        }
        if (r6_memcmp(episode.name, name, length) == 0 &&
                episode.name[length] == 0) {
            return (int)i;
        }
    }
    return -1;
}

int r6_story_catalog_find_key(const r6_story_catalog *catalog,
                              const char *key) {
    size_t i;
    size_t length;
    if (!catalog || !catalog->keys || !catalog->strings || !key) {
        return -1;
    }
    length = r6_strlen(key);
    if (!length) {
        return -1;
    }
    for (i = 0; i < catalog->key_count; i++) {
        r6_story_key row;
        if (r6_story_catalog_key(catalog, i, &row) != R6_OK ||
                row.id_len != length ||
                row.id_offset > catalog->string_count ||
                row.id_len > catalog->string_count - row.id_offset) {
            return -1;
        }
        if (r6_memcmp(catalog->strings + row.id_offset, key, length) == 0) {
            return (int)i;
        }
    }
    return -1;
}
