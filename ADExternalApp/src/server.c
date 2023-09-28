#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>

#include <sys/epoll.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>

#include "server.h"

#define MAX_SERVER_CLIENTS 8
#define MAX_EVENTS (MAX_SERVER_CLIENTS * 4)
#define MAX_SOCK_PATH_LENGTH 107


struct server_connection {
    bool used;
    bool closed;
    struct server_context *server;
    int sock;
    time_t last_msg_time;
    void *send_buffer;
    size_t send_nbytes;
    bool need_send;
    void *private;
};


struct server_context {
    int listening_sock;
    int epoll;
    char sock_path[MAX_SOCK_PATH_LENGTH + 1];
    struct server_connection connections[MAX_SERVER_CLIENTS];
    struct server_connection_event events[MAX_EVENTS];
    size_t event_tail_index;
    size_t event_head_index;
    uint32_t dropped_connections;
};


static int listen_new_socket(const char *path)
{
    // Using SOCK_SEQPACKET simplifies a lot, message boundaries are preserved
    int sock = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_NONBLOCK, 0);
    struct sockaddr_un addr = { .sun_family = AF_UNIX };
    strncpy(addr.sun_path, path, MAX_SOCK_PATH_LENGTH);

    if (bind(sock, (struct sockaddr *) &addr, sizeof(struct sockaddr_un)) == -1) {
        printf("server: error binding unix socket\n");
        return -1;
    }

    if (listen(sock, 1)) {
        printf("server: error listening unix socket\n");
        return -1;
    }

    return sock;
}


static struct server_connection *server_get_connection_by_socket(
    struct server_context *server, int sock)
{
    for (size_t i=0; i < MAX_SERVER_CLIENTS; i++) {
        if (server->connections[i].sock == sock)
            return &server->connections[i];
    }
    return (struct server_connection *) NULL;
}


static void server_connection_add_event(
    struct server_connection *connection, enum server_connection_event_type type)
{
    struct server_context *server = connection->server;
    server->events[server->event_tail_index] = (struct server_connection_event) {
        .connection = connection,
        .type = type
    };

    server->event_tail_index = (server->event_tail_index + 1) % MAX_EVENTS;
}


static struct server_connection *server_connection_create(struct server_context *server)
{
    struct epoll_event ev;
    int new_client;
    struct server_connection *connection = NULL;
    if((new_client=accept4(
            server->listening_sock, NULL, NULL, SOCK_NONBLOCK)) == -1) {
        server->dropped_connections++;
        printf("server: can't accept new client\n");
        return (struct server_connection *) NULL;
    }

    for (size_t i=0; i < MAX_SERVER_CLIENTS; i++) {
        if (!server->connections[i].used) {
            connection = &server->connections[i];
            break;
        }
    }

    if (connection == NULL) {
        // no slots to handle new client
        close(new_client);
        server->dropped_connections++;
        return (struct server_connection *) NULL;
    }

    connection->used = true;
    connection->closed = false;
    connection->last_msg_time = time(NULL);
    connection->sock = new_client;
    connection->private = NULL;
    ev.events = EPOLLIN;
    ev.data.fd = new_client;
    // TODO: handle epoll errors
    epoll_ctl(server->epoll, EPOLL_CTL_ADD, new_client, &ev);
    server_connection_add_event(connection, SCONNECTION_EVENT_CREATE);
    return connection;
}


void server_connection_close(struct server_connection *connection)
{
    epoll_ctl(connection->server->epoll, EPOLL_CTL_DEL, connection->sock, NULL);
    close(connection->sock);
    server_connection_add_event(connection, SCONNECTION_EVENT_CLOSED);
    connection->closed = true;
}


struct server_context *server_create(const char *path)
{
    struct epoll_event ev;
    struct server_context *server = calloc(sizeof(struct server_context), 1);
    strncpy(server->sock_path, path, MAX_SOCK_PATH_LENGTH);
    if (access(server->sock_path, F_OK) == 0) {
        printf("server: path exists ... trying to remove\n");
        unlink(server->sock_path);
    }
    server->listening_sock = listen_new_socket(path);
    server->epoll = epoll_create1(0);
    ev.events = EPOLLIN;
    ev.data.fd = server->listening_sock;
    // TODO: handle epoll errors
    epoll_ctl(server->epoll, EPOLL_CTL_ADD, server->listening_sock, &ev);
    for (size_t i=0; i < MAX_SERVER_CLIENTS; i++) {
        server->connections[i].server = server;
    }
    return server;
}


void server_destroy(struct server_context *server)
{
    close(server->listening_sock);
    for(size_t i=0; i < MAX_SERVER_CLIENTS; i++) {
        if(server->connections[i].used) {
            server_connection_close(&server->connections[i]);
            server_connection_destroy(&server->connections[i]);
        }
    }
    close(server->epoll);
    unlink(server->sock_path);
    free(server);
}


void server_connection_destroy(struct server_connection *connection)
{
    connection->used = false;
}


void server_close_dead_connections(struct server_context *server, int timeout)
{
    time_t limit_time = time(NULL) + timeout;
    for (size_t i=0; i < MAX_SERVER_CLIENTS; i++) {
        struct server_connection *connection = &server->connections[i];
        if (connection->used
                && !connection->closed
                && connection->last_msg_time >= limit_time) {
            server_connection_close(connection);
        }
    }
}


struct server_connection_event server_pop_event(struct server_context *server)
{
    if (server->event_head_index == server->event_tail_index) {
        return (struct server_connection_event) {
            .connection = (struct server_connection *) NULL,
            .type = SCONNECTION_EVENT_NONE
        };
    }

    struct server_connection_event event = server->events[server->event_head_index];
    server->event_head_index = (server->event_head_index + 1) % MAX_EVENTS;
    return event;
}


void server_poll(struct server_context *server, int timeout_msec)
{
    struct epoll_event events[MAX_EVENTS];
    int nfds;
    struct server_connection *connection;

    nfds = epoll_wait(server->epoll, events, MAX_EVENTS, timeout_msec);

    if (nfds == -1) {
        if (errno == EINTR)
            nfds = 0;
        else
            return;
    }

    server->event_head_index = server->event_tail_index = 0;

    for (int i=0; i < nfds; i++) {
        if (events[i].data.fd == server->listening_sock) {
            connection = server_connection_create(server);
            // no slot available
            if (connection == NULL) {
                continue;
            }
        } else {
            connection = server_get_connection_by_socket(
                server, events[i].data.fd);
            connection->last_msg_time = time(NULL);
            server_connection_add_event(connection, SCONNECTION_EVENT_IN);
        }
    }
}



// round robin between open connections
struct server_connection *server_next_connection(struct server_context *server)
{
    static size_t current_index = 0;
    for (size_t i=0; i < MAX_SERVER_CLIENTS; i++) {
        struct server_connection *connection = &server->connections[current_index];
        current_index = (current_index + 1) % MAX_SERVER_CLIENTS;
        if (!connection->closed && connection->used)
            return connection;
    }
    return (struct server_connection *) NULL;
}


void server_connection_set_private(struct server_connection *connection, void *priv)
{
    connection->private = priv;
}


void *server_connection_get_private(struct server_connection *connection)
{
    return connection->private;
}

int server_connection_get_socket(struct server_connection *connection)
{
    return connection->sock;
}

