#ifndef _LIST_H
#define _LIST_H

// copied from linux's list.h

struct list_head {
    struct list_head *next, *prev;
};

static inline int list_empty(struct list_head *list)
{
    return list->next == list;
}

static inline void INIT_LIST_HEAD(struct list_head *list)
{
    list->next = list->prev = list;
}

static inline void list_add(struct list_head *newn, struct list_head *head)
{
    newn->prev = head;
    newn->next = head->next;
    newn->prev->next = newn;
    newn->next->prev = newn;
}

static inline void list_del(struct list_head *entry)
{
    entry->prev->next = entry->next;
    entry->next->prev = entry->prev;
}

#define list_for_each(pos, head) \
    for (pos = (head)->next; pos != (head); pos = pos->next)

#define list_for_each_safe(pos, tmp, head) \
    for (pos = (head)->next, tmp = pos->next; pos != head; \
         pos = tmp, tmp = tmp->next)

#define container_of(ptr, type, member) \
    ((type *) ((char *) ptr - offsetof(type, member)))

#define list_entry(ptr, type, member) container_of(ptr, type, member)

#define list_first_entry(ptr, type, member) \
    list_entry((ptr)->next, type, member)
#define list_last_entry(ptr, type, member) \
    list_entry((ptr)->prev, type, member)
#define list_next_entry(pos, member) list_entry((pos)->member.next, typeof(*(pos)), member)
#define list_entry_is_head(pos, head, member) (&pos->member == (head))

#define list_for_each_entry(pos, head, member) \
     for (pos = list_first_entry(head, typeof(*pos), member); \
          !list_entry_is_head(pos, head, member); \
          pos = list_next_entry(pos, member))

#define list_for_each_entry_safe(pos, tmp, head, member) \
     for (pos = list_first_entry(head, typeof(*pos), member), tmp = list_next_entry(pos, member); \
          !list_entry_is_head(pos, head, member); \
          pos = tmp, tmp = list_next_entry(tmp, member))

#endif
