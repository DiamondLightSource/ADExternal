#ifndef _SERVER_H_
#define _SERVER_H_

#ifdef __cplusplus
extern "C" {
#endif

struct server_context;
struct server_connection;

enum server_connection_event_type {
    SCONNECTION_EVENT_NONE,
    SCONNECTION_EVENT_CREATE,
    SCONNECTION_EVENT_IN,
    SCONNECTION_EVENT_CLOSED
};

struct server_connection_event {
    struct server_connection *connection;
    enum server_connection_event_type type;
};

struct server_context *server_create(const char *path);

void server_destroy(struct server_context *server);

void server_close_dead_connections(struct server_context *server, int timeout);

void server_connection_close(struct server_connection *connection);

void server_connection_destroy(struct server_connection *connection);

struct server_connection_event server_pop_event(struct server_context *server);

void server_poll(struct server_context *server, int timeout_msec);

struct server_connection *server_next_connection(struct server_context *server);

void server_connection_set_private(struct server_connection *connection, void *priv);

void *server_connection_get_private(struct server_connection *connection);

int server_connection_get_socket(struct server_connection *connection);

#ifdef __cplusplus
}
#endif

#endif
