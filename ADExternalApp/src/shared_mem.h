#ifndef _SHARED_MEM_H_
#define _SHARED_MEM_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include <stddef.h>

#include "list.h"

#define MAX_SHM_PATH 64

struct shared_mem_context {
    void *addr;
    size_t size;
    char path[MAX_SHM_PATH];
    struct list_head free_list;
    struct list_head used_list;
};

static inline bool shared_mem_is_included(
    struct shared_mem_context *context, void *addr)
{
    return addr >= context->addr &&
        (char *) addr < (char *) context->addr + context->size;
}

struct shared_mem_context *shared_mem_create(const char *name, size_t size);

void shared_mem_destroy(struct shared_mem_context *context);

void shared_mem_print(struct shared_mem_context *context);

void *shared_mem_malloc(struct shared_mem_context *context, size_t size);

void shared_mem_free(struct shared_mem_context *context, void *ptr);

#ifdef __cplusplus
}
#endif

#endif
