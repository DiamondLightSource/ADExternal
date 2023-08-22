#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <sys/mman.h>

#include "shared_mem.h"


struct mem_area {
    struct list_head list;
    void *start;
    size_t size;
};


static inline bool _mem_area_can_merge(struct mem_area *a1, struct mem_area *a2)
{
    return a1->start + a1->size == a2->start ||
        a2->start + a2->size == a1->start;
}


static inline void _mem_area_merge(struct mem_area *dst, struct mem_area *src)
{
    if (dst->start + dst->size == src->start) {
        dst->size += src->size;
    } else if (src->start + src->size == dst->start) {
        dst->start = src->start;
        dst->size += src->size;
    }
}


static inline void _mem_area_add_free(
    struct shared_mem_context *context, struct mem_area *area)
{
    struct mem_area *pos;
    list_for_each_entry(pos, &context->free_list, list) {
        if (pos->start > area->start) {
            list_add(&area->list, pos->list.prev);
            return;
        }
    }
    list_add(&area->list, &context->free_list);
}


void *shared_mem_malloc(struct shared_mem_context *context, size_t size)
{
    struct mem_area *pos, *tmp;
    if (size < 16)
        size = 16;

    list_for_each_entry_safe(pos, tmp, &context->free_list, list) {
        if (pos->size >= size) {
            if (pos->size > size) {
                struct mem_area *new =
                    (struct mem_area *) malloc(sizeof(struct mem_area));
                new->start = pos->start + size;
                new->size = pos->size - size;
                pos->size = size;
                list_add(&new->list, pos->list.prev);
            }
            list_del(&pos->list);
            list_add(&pos->list, &context->used_list);
            return pos->start;
        }
    }

    return NULL;
}


void shared_mem_free(struct shared_mem_context *context, void *ptr)
{
    struct mem_area *pos, *tmp, *area = NULL;
    list_for_each_entry(pos, &context->used_list, list) {
        if (pos->start == ptr) {
            area = pos;
            list_del(&pos->list);
            break;
        }
    }
    if (!area) {
        printf("shared_mem: tried to free unknown memory area\n");
        return;
    }
    list_for_each_entry_safe(pos, tmp, &context->free_list, list) {
        if (_mem_area_can_merge(area, pos)) {
            _mem_area_merge(area, pos);
            list_del(&pos->list);
            free(pos);
        }
    }
    _mem_area_add_free(context, area);
}


struct shared_mem_context *shared_mem_create(const char *name, size_t size)
{
    struct shared_mem_context *context =
        (struct shared_mem_context *) malloc(sizeof(struct shared_mem_context));
    context->size = size;
    strncpy(context->path, "/dev/shm/", MAX_SHM_PATH);
    strncat(context->path, name, MAX_SHM_PATH - 9);
    int fd = open(
        context->path, O_RDWR | O_CREAT, S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP);
    int rc = ftruncate(fd, size);
    if (fd < 0 || rc < 0)
        goto err_out;

    context->addr = mmap(
        NULL, context->size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (context->addr == MAP_FAILED)
        goto err_out;

    INIT_LIST_HEAD(&context->free_list);
    INIT_LIST_HEAD(&context->used_list);
    struct mem_area *area = (struct mem_area *) malloc(sizeof(struct mem_area));
    area->start = context->addr;
    area->size = context->size;
    _mem_area_add_free(context, area);

    return context;
err_out:
    free(context);
    return NULL;
}


void shared_mem_print(struct shared_mem_context *context)
{
    struct mem_area *pos;
    int i=0;
    list_for_each_entry(pos, &context->free_list, list) {
        printf("free area %d: start=%p size=%lu\n", i++, pos->start, pos->size);
    }
    i = 0;
    list_for_each_entry(pos, &context->used_list, list) {
        printf("used area %d: start=%p size=%lu\n", i++, pos->start, pos->size);
    }
}


void shared_mem_destroy(struct shared_mem_context *context)
{
    munmap(context->addr, context->size);
    unlink(context->path);
    free(context);
}
