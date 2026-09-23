#ifndef MGCP_PROTOCOL_H
#define MGCP_PROTOCOL_H

#include <switch.h>

#define MGCP_DEFAULT_PORT 2427
#define MGCP_SERVER_PORT 2727
/* ShoreTel "Remote" control channel — binary type-0x10 messages arrive here,
   separate from the MGCP UDP. Phone is the client; we listen. */
#define MGCP_REMOTE_TCP_PORT 5000

/* Represents the state of a ShoreTel/MGCP endpoint */
typedef struct mgcp_endpoint_s {
    char name[128];                 /* The ShoreTel MAC e.g. SHOR_001049421B38 */
    char extension[32];             /* Extension assigned to this endpoint (from directory) */
    char ip[48];                    /* The last known IP of the phone */
    switch_port_t port;             /* The last known port of the phone (usually 2427) */
    switch_sockaddr_t *addr;        /* Parsed sockaddr for replies */

    int on_hook;                    /* 1 = on hook, 0 = off hook */
    int next_trans_id;              /* Rolling transaction ID for requests *to* the phone */

    /* Registration / connection state */
    int pending_type;               /* MGCP_PEND_* — which response we are awaiting */
    int pending_trans_id;           /* Transaction ID of the in-flight request */
    int audit_pending;              /* send AUEP after the current RQNT is acked */
    int dialtone_retried;           /* Set once if we retried dial tone after a 402 */
    char call_id[64];               /* Call-Id of the current connection (from CRCX) */
    char connection_id[64];         /* Connection-Id returned by CRCX (I: header) */
    int has_connection;             /* 1 = a connection is currently established */
    char capabilities[2048];        /* AUEP A: response (codecs / packages) */
    char sdp[4096];                 /* SDP returned by CRCX */

    switch_core_session_t *session; /* The active FreeSWITCH session, if any */

    struct mgcp_endpoint_s *next;
} mgcp_endpoint_t;

/* Global state for the module */
typedef struct mgcp_globals_s {
    switch_memory_pool_t *pool;
    switch_socket_t *socket;
    int running;
    switch_endpoint_interface_t *endpoint_interface;
    mgcp_endpoint_t *endpoints;
    switch_mutex_t *endpoints_mutex;
    switch_thread_t *listener_thread;
    switch_socket_t *tcp_socket;    /* ShoreTel "Remote" TCP listener (port 5000) */
    switch_thread_t *tcp_thread;    /* Accept + log thread for the TCP channel */
} mgcp_globals_t;

extern mgcp_globals_t mgcp_globals;
extern switch_state_handler_table_t mgcp_state_handlers;
extern switch_io_routines_t mgcp_io_routines;


/* Protocol functions */
switch_status_t mgcp_protocol_init(switch_memory_pool_t *pool, switch_endpoint_interface_t *endpoint_interface);
switch_status_t mgcp_protocol_destroy(void);

/* Process an incoming packet */
void mgcp_handle_packet(char *buf, switch_size_t len, switch_sockaddr_t *from_addr);

/* Endpoint management */
mgcp_endpoint_t *mgcp_endpoint_find_or_create(const char *name, const char *ip, switch_port_t port, switch_sockaddr_t *addr);

/* Send a message to the endpoint */
void mgcp_send_message(mgcp_endpoint_t *ep, const char *msg);

#endif /* MGCP_PROTOCOL_H */
