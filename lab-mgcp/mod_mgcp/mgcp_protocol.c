#include "mgcp_protocol.h"
#include <ctype.h>
#include <stdlib.h>
#include <string.h>

mgcp_globals_t mgcp_globals;
static uint32_t mgcp_call_seq = 0;

/* Extension/identity: the phone is identified by its MGCP endpoint name
   (SHOR_<MAC>); the extension is resolved from the FreeSWITCH directory by that
   MAC, falling back to the default below when no directory entry matches. */
#define MGCP_DEFAULT_EXTENSION "4001"

/* Look up a phone's extension in the FreeSWITCH directory by MAC. The directory
   maps MAC -> user via a variable named "mgcp_mac":
       <user id="4001">
         <variables>
           <variable name="mgcp_mac" value="001049421b38"/>
         </variables>
       </user>
   Returns the user id (extension), or NULL if no match. Iterates every domain's
   users (same pattern mod_sofia uses to resolve directory users). */
static const char *mgcp_directory_lookup_extension(const char *mac)
{
    switch_xml_t xml_root = NULL, x_domains = NULL;
    switch_xml_t x_domain, x_groups, x_group, x_users, x_user, x_var;
    const char *ext = NULL;

    if (switch_xml_locate("directory", NULL, NULL, NULL, &xml_root, &x_domains, NULL, SWITCH_FALSE) != SWITCH_STATUS_SUCCESS) {
        return NULL;
    }

    /* Directory layout: <section><domain><groups><group><users><user>. */
    for (x_domain = switch_xml_child(x_domains, "domain"); x_domain; x_domain = x_domain->next) {
        x_groups = switch_xml_child(x_domain, "groups");
        for (x_group = switch_xml_child(x_groups, "group"); x_group; x_group = x_group->next) {
            x_users = switch_xml_child(x_group, "users");
            for (x_user = switch_xml_child(x_users, "user"); x_user; x_user = x_user->next) {
                switch_xml_t x_vars = switch_xml_child(x_user, "variables");
                for (x_var = switch_xml_child(x_vars, "variable"); x_var; x_var = x_var->next) {
                    const char *name = switch_xml_attr_soft(x_var, "name");
                    const char *value = switch_xml_attr_soft(x_var, "value");
                    if (name && value && !strcasecmp(name, "mgcp_mac") && !strcasecmp(value, mac)) {
                        ext = switch_xml_attr_soft(x_user, "id");
                        goto done;
                    }
                }
            }
        }
    }

done:
    /* clone=SWITCH_FALSE: xml_root is a reference into the master tree — do not free */
    return ext;
}

/* Resolve the extension for an endpoint from its name (SHOR_<MAC>) via the
   directory, storing the result in ep->extension (fallback = default). */
static void mgcp_resolve_extension(mgcp_endpoint_t *ep)
{
    const char *mac = ep->name;
    const char *ext;

    if (!strncasecmp(mac, "SHOR_", 5)) {
        mac += 5;   /* strip the "SHOR_" prefix, leaving the MAC */
    }

    ext = mgcp_directory_lookup_extension(mac);
    switch_copy_string(ep->extension, ext ? ext : MGCP_DEFAULT_EXTENSION, sizeof(ep->extension));

    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO,
                      "Resolved extension %s for %s (MAC %s)%s\n",
                      ep->extension, ep->name, mac, ext ? "" : " [default]");
}

/* Build the RFC 3149 line-appearance signal string for an endpoint's extension
   (KY/ls labels feature key 1, KY/ks marks it idle). Static buffer — safe here
   because the listener thread handles packets serially. */
static const char *mgcp_line_signals(mgcp_endpoint_t *ep)
{
    static char buf[96];
    snprintf(buf, sizeof(buf), "KY/ls(1,%s), KY/ks(1,id)", ep->extension);
    return buf;
}

/* Digit events (RFC 3435 DTMF package). The ShoreTel phone also emits a "u/ku(N)"
   key-up event alongside each digit; star and pound are omitted until their exact
   names are confirmed (the phone rejects them with 511). */
#define MGCP_OFFHOOK_EVENTS "L/hu(N), L/hf(N), d/0(N), d/1(N), d/2(N), d/3(N), d/4(N), d/5(N), d/6(N), d/7(N), d/8(N), d/9(N)"

/* Pending operation types — what response we are currently awaiting */
enum {
    MGCP_PEND_NONE = 0,
    MGCP_PEND_AUEP,   /* awaiting AUEP (capabilities audit) response    */
    MGCP_PEND_CRCX,   /* awaiting CRCX (create connection) response     */
    MGCP_PEND_DLCX,   /* awaiting DLCX (delete connection) response     */
    MGCP_PEND_RQNT    /* awaiting RQNT (notification request) response  */
};

/* UDP listener thread */
static void *SWITCH_THREAD_FUNC mgcp_listener_thread(switch_thread_t *thread, void *obj)
{
    switch_sockaddr_t *from_addr;
    char buf[4096];
    switch_size_t len;
    switch_status_t status;

    switch_sockaddr_info_get(&from_addr, NULL, SWITCH_UNSPEC, 0, 0, mgcp_globals.pool);

    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "mod_mgcp listening for packets on UDP %d...\n", MGCP_SERVER_PORT);

    while (mgcp_globals.running) {
        len = sizeof(buf) - 1;
        status = switch_socket_recvfrom(from_addr, mgcp_globals.socket, 0, buf, &len);

        if (status == SWITCH_STATUS_SUCCESS && len > 0) {
            buf[len] = '\0';
            mgcp_handle_packet(buf, len, from_addr);
        } else {
            /* No data (socket is non-blocking) — yield briefly so that
               mgcp_protocol_destroy() can set running=0 and join us. */
            switch_yield(10000);
        }
    }
    return NULL;
}

/* Hex + ASCII dump of bytes received on the ShoreTel "Remote" TCP channel */
static void mgcp_tcp_log_dump(const char *ip, const char *buf, switch_size_t len)
{
    char hex[4096], ascii[1024];
    switch_size_t i, h = 0, a = 0;
    hex[0] = '\0';
    ascii[0] = '\0';
    for (i = 0; i < len && h < sizeof(hex) - 4; i++) {
        h += snprintf(hex + h, sizeof(hex) - h, "%02x ", (unsigned char)buf[i]);
        if (a < sizeof(ascii) - 2) {
            ascii[a++] = (buf[i] >= 0x20 && buf[i] < 0x7f) ? buf[i] : '.';
            ascii[a] = '\0';
        }
    }
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO,
                      "mod_mgcp TCP[%s] %d bytes: %s| %s\n", ip, (int)len, hex, ascii);
}

/* Accept + log everything the phone sends on the ShoreTel "Remote" TCP channel
   (port 5000). The phone is the client; we listen and dump the binary frames so
   the type-0x10 "connected" message (and the full frame layout) can be observed. */
static void *SWITCH_THREAD_FUNC mgcp_tcp_listener_thread(switch_thread_t *thread, void *obj)
{
    switch_sockaddr_t *addr, *client_addr;
    switch_socket_t *client_sock = NULL;
    char buf[4096];
    switch_size_t len;
    char ip[48];

    if (switch_sockaddr_info_get(&addr, "0.0.0.0", SWITCH_UNSPEC, MGCP_REMOTE_TCP_PORT, 0, mgcp_globals.pool) != SWITCH_STATUS_SUCCESS) {
        switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_ERROR, "mod_mgcp: bad Remote TCP addr\n");
        return NULL;
    }

    if (switch_socket_create(&mgcp_globals.tcp_socket, switch_sockaddr_get_family(addr), SOCK_STREAM, 0, mgcp_globals.pool) != SWITCH_STATUS_SUCCESS) {
        switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_ERROR, "mod_mgcp: failed to create Remote TCP socket\n");
        return NULL;
    }

    switch_socket_opt_set(mgcp_globals.tcp_socket, SWITCH_SO_REUSEADDR, 1);
    switch_socket_opt_set(mgcp_globals.tcp_socket, SWITCH_SO_NONBLOCK, 1);

    if (switch_socket_bind(mgcp_globals.tcp_socket, addr) != SWITCH_STATUS_SUCCESS) {
        switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_ERROR, "mod_mgcp: failed to bind Remote TCP port %d\n", MGCP_REMOTE_TCP_PORT);
        switch_socket_close(mgcp_globals.tcp_socket);
        mgcp_globals.tcp_socket = NULL;
        return NULL;
    }

    switch_socket_listen(mgcp_globals.tcp_socket, 5);

    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO,
                      "mod_mgcp listening for ShoreTel 'Remote' TCP on port %d...\n", MGCP_REMOTE_TCP_PORT);

    while (mgcp_globals.running) {
        client_sock = NULL;
        if (switch_socket_accept(&client_sock, mgcp_globals.tcp_socket, mgcp_globals.pool) == SWITCH_STATUS_SUCCESS && client_sock) {
            switch_socket_addr_get(&client_addr, SWITCH_TRUE, client_sock);
            switch_get_addr(ip, sizeof(ip), client_addr);
            switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "mod_mgcp: Remote TCP connection from %s\n", ip);
            switch_socket_opt_set(client_sock, SWITCH_SO_NONBLOCK, 1);

            /* Send the "connected" frame (type 0x10, sub-type 2) to flip soisconnected.
               Candidate frame from the ROM — adjust once we see the phone's own bytes. */
            {
                static const char connect_frame[] = {
                    0x11, 0x00, 0x04, 0x00,   /* header (magic + len 4) */
                    0x10, 0x02, 0x00, 0x00,   /* type 0x10, sub-type 2, 2 reserved */
                    0x00, 0x00, 0x00, 0x00    /* u32 value -> ep+0x28 */
                };
                switch_size_t flen = sizeof(connect_frame);
                if (switch_socket_send(client_sock, connect_frame, &flen) == SWITCH_STATUS_SUCCESS) {
                    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO,
                                      "mod_mgcp: sent %d-byte connected frame to %s\n", (int)flen, ip);
                }
            }

            for (;;) {
                switch_status_t st;
                len = sizeof(buf);
                st = switch_socket_recv(client_sock, buf, &len);
                if (st == SWITCH_STATUS_SUCCESS) {
                    if (len > 0) {
                        mgcp_tcp_log_dump(ip, buf, len);
                        continue;
                    }
                    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "mod_mgcp: Remote TCP %s closed\n", ip);
                    break;
                }
                if (!mgcp_globals.running) {
                    break;
                }
                switch_yield(10000);
            }
            switch_socket_close(client_sock);
        } else {
            switch_yield(10000);
        }
    }

    if (mgcp_globals.tcp_socket) {
        switch_socket_close(mgcp_globals.tcp_socket);
        mgcp_globals.tcp_socket = NULL;
    }
    return NULL;
}

switch_status_t mgcp_protocol_init(switch_memory_pool_t *pool, switch_endpoint_interface_t *endpoint_interface)
{
    switch_sockaddr_t *addr;
    switch_threadattr_t *thd_attr;

    memset(&mgcp_globals, 0, sizeof(mgcp_globals));
    mgcp_globals.pool = pool;
    mgcp_globals.endpoint_interface = endpoint_interface;
    switch_mutex_init(&mgcp_globals.endpoints_mutex, SWITCH_MUTEX_NESTED, mgcp_globals.pool);

    if (switch_sockaddr_info_get(&addr, "0.0.0.0", SWITCH_UNSPEC, MGCP_SERVER_PORT, 0, mgcp_globals.pool) != SWITCH_STATUS_SUCCESS) {
        return SWITCH_STATUS_FALSE;
    }

    if (switch_socket_create(&mgcp_globals.socket, switch_sockaddr_get_family(addr), SOCK_DGRAM, 0, mgcp_globals.pool) != SWITCH_STATUS_SUCCESS) {
        return SWITCH_STATUS_FALSE;
    }

    switch_socket_opt_set(mgcp_globals.socket, SWITCH_SO_REUSEADDR, 1);
    switch_socket_opt_set(mgcp_globals.socket, SWITCH_SO_NONBLOCK, 1);

    if (switch_socket_bind(mgcp_globals.socket, addr) != SWITCH_STATUS_SUCCESS) {
        switch_socket_close(mgcp_globals.socket);
        return SWITCH_STATUS_FALSE;
    }

    mgcp_globals.running = 1;
    switch_threadattr_create(&thd_attr, mgcp_globals.pool);
    switch_thread_create(&mgcp_globals.listener_thread, thd_attr, mgcp_listener_thread, NULL, mgcp_globals.pool);
    switch_thread_create(&mgcp_globals.tcp_thread, thd_attr, mgcp_tcp_listener_thread, NULL, mgcp_globals.pool);

    return SWITCH_STATUS_SUCCESS;
}

switch_status_t mgcp_protocol_destroy(void)
{
    mgcp_globals.running = 0;
    /* Join the listener thread FIRST (it exits within one poll cycle now that
       the socket is non-blocking), then close the socket — never the reverse,
       or the thread would touch a freed socket. */
    if (mgcp_globals.listener_thread) {
        switch_status_t st = SWITCH_STATUS_FALSE;
        switch_thread_join(&st, mgcp_globals.listener_thread);
        mgcp_globals.listener_thread = NULL;
    }
    if (mgcp_globals.socket) {
        switch_socket_close(mgcp_globals.socket);
        mgcp_globals.socket = NULL;
    }
    if (mgcp_globals.tcp_thread) {
        switch_status_t st = SWITCH_STATUS_FALSE;
        switch_thread_join(&st, mgcp_globals.tcp_thread);
        mgcp_globals.tcp_thread = NULL;
    }
    return SWITCH_STATUS_SUCCESS;
}

mgcp_endpoint_t *mgcp_endpoint_find_or_create(const char *name, const char *ip, switch_port_t port, switch_sockaddr_t *addr)
{
    mgcp_endpoint_t *ep = NULL;

    switch_mutex_lock(mgcp_globals.endpoints_mutex);

    for (ep = mgcp_globals.endpoints; ep; ep = ep->next) {
        if (!strcasecmp(ep->name, name)) {
            break;
        }
    }

    if (!ep) {
        ep = switch_core_alloc(mgcp_globals.pool, sizeof(mgcp_endpoint_t));
        switch_copy_string(ep->name, name, sizeof(ep->name));
        ep->on_hook = 1; /* Assume on-hook at boot */
        ep->next_trans_id = 1000;
        ep->next = mgcp_globals.endpoints;
        mgcp_globals.endpoints = ep;
        switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "Created new MGCP endpoint: %s\n", ep->name);
    }

    /* Always update the network location, it might have changed */
    switch_copy_string(ep->ip, ip, sizeof(ep->ip));
    ep->port = port;

    /* We duplicate the sockaddr so we can use it asynchronously */
    if (!ep->addr) {
        switch_sockaddr_info_get(&ep->addr, ip, SWITCH_UNSPEC, port, 0, mgcp_globals.pool);
    }

    switch_mutex_unlock(mgcp_globals.endpoints_mutex);

    return ep;
}

/* Find an endpoint by source IP:port (used to correlate responses) */
static mgcp_endpoint_t *mgcp_endpoint_find_by_addr(const char *ip, switch_port_t port)
{
    mgcp_endpoint_t *ep;

    switch_mutex_lock(mgcp_globals.endpoints_mutex);
    for (ep = mgcp_globals.endpoints; ep; ep = ep->next) {
        if (ep->port == port && !strcmp(ep->ip, ip)) {
            break;
        }
    }
    switch_mutex_unlock(mgcp_globals.endpoints_mutex);

    return ep;
}

void mgcp_send_message(mgcp_endpoint_t *ep, const char *msg)
{
    switch_size_t len = strlen(msg);
    if (ep->addr && mgcp_globals.socket) {
        switch_socket_sendto(mgcp_globals.socket, ep->addr, 0, msg, &len);
        switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "TX to %s:%d\n---\n%s---\n", ep->ip, ep->port, msg);
    }
}

/* --- Registration / call-control request senders --------------------------- */

/* AUEP with F: A — audit the endpoint for its full capability set.
   Without F: A the phone answers with a bare 200 and no capabilities. */
static void mgcp_send_auep(mgcp_endpoint_t *ep)
{
    char msg[512];

    ep->pending_trans_id = ep->next_trans_id++;
    ep->pending_type = MGCP_PEND_AUEP;
    snprintf(msg, sizeof(msg),
        "AUEP %d %s@[%s] MGCP 1.0\n"
        "F: A,R,S,D\n",
        ep->pending_trans_id, ep->name, ep->ip);
    mgcp_send_message(ep, msg);
}

/* CRCX — create the phone's media connection. This is the step that takes the
   phone out of "Requesting Service": without an established connection it keeps
   re-RSIPing "RM: disconnected" every ~120s.

   The phone rejects `M: sendrecv` with 527 (Missing RemoteConnectionDescriptor)
   unless we supply our SDP, and it ignores an `M: inactive` connection (stays
   "disconnected"). So we offer PCMU and provide our media endpoint.

   Media/SRTP note: the phone speaks standard SRTP (RFC 3711) — AES_CM_128_HMAC
   SHA1_80/32, key exchange via SDES (RFC 4568) a=crypto:... inline:<key>.
   Without an a=crypto: line the call stays plaintext RTP (the current default).
   To enable encryption later, append e.g.
       a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:<base64 key+salt>
   to this SDP and use libsrtp to protect/unprotect the RTP on port 5004. */
#define MGCP_SDP_HOST_IP "192.168.18.20"   /* lab host IP as the phone sees us */
#define MGCP_SDP_RTP_PORT 5004              /* ShoreTel phones only RTP on 5004 */

static void mgcp_send_crcx(mgcp_endpoint_t *ep)
{
    char msg[2048];

    mgcp_call_seq++;
    snprintf(ep->call_id, sizeof(ep->call_id), "%08x%08x",
             mgcp_call_seq, (unsigned int)(switch_micro_time_now() & 0xffffffffu));

    ep->pending_trans_id = ep->next_trans_id++;
    ep->pending_type = MGCP_PEND_CRCX;
    snprintf(msg, sizeof(msg),
        "CRCX %d %s@[%s] MGCP 1.0\n"
        "C: %s\n"
        "L: p:20, a:PCMU\n"
        "M: sendrecv\n"
        "X: %d\n"
        "\n"
        "v=0\n"
        "o=- %u %u IN IP4 %s\n"
        "s=-\n"
        "c=IN IP4 %s\n"
        "t=0 0\n"
        "m=audio %d RTP/AVP 0\n"
        "a=rtpmap:0 PCMU/8000\n",
        ep->pending_trans_id, ep->name, ep->ip, ep->call_id, ep->pending_trans_id,
        mgcp_call_seq, mgcp_call_seq, MGCP_SDP_HOST_IP, MGCP_SDP_HOST_IP, MGCP_SDP_RTP_PORT);
    mgcp_send_message(ep, msg);
}

/* DLCX — tear down the current connection (using the real IDs, not "0"). */
static void mgcp_send_dlcx(mgcp_endpoint_t *ep)
{
    char msg[512];

    ep->pending_trans_id = ep->next_trans_id++;
    ep->pending_type = MGCP_PEND_DLCX;
    snprintf(msg, sizeof(msg),
        "DLCX %d %s@[%s] MGCP 1.0\n"
        "C: %s\n"
        "I: %s\n",
        ep->pending_trans_id, ep->name, ep->ip, ep->call_id, ep->connection_id);
    mgcp_send_message(ep, msg);
}

/* RQNT — arm event monitoring. `signals == NULL` omits the S: line entirely;
   `signals == ""` emits an empty S: (stops any in-progress signal). */
static void mgcp_send_rqnt(mgcp_endpoint_t *ep, const char *events, const char *signals,
                           const char *disp1, const char *disp2)
{
    char msg[1024];
    int len;

    ep->pending_trans_id = ep->next_trans_id++;
    ep->pending_type = MGCP_PEND_RQNT;
    len = snprintf(msg, sizeof(msg),
        "RQNT %d %s@[%s] MGCP 1.0\n"
        "X: %d\n"
        "R: %s\n",
        ep->pending_trans_id, ep->name, ep->ip, ep->pending_trans_id, events);
    if (signals) {
        len += snprintf(msg + len, sizeof(msg) - len, "S: %s\n", signals);
    }
    if (disp1 && disp1[0] != '\0') {
        len += snprintf(msg + len, sizeof(msg) - len, "X-ShoreDisplay: %s\n", disp1);
    }
    if (disp2 && disp2[0] != '\0') {
        len += snprintf(msg + len, sizeof(msg) - len, "X-ShoreDisplay2: %s\n", disp2);
    }
    mgcp_send_message(ep, msg);
}

/* --- Response handling ----------------------------------------------------- */

static void mgcp_handle_response(mgcp_endpoint_t *ep, int code, const char *trans_id,
                                 char **lines, int num_lines)
{
    int i, tid = atoi(trans_id);

    if (ep->pending_type == MGCP_PEND_NONE || tid != ep->pending_trans_id) {
        /* Unsolicited or out-of-order response — ignore */
        return;
    }

    switch (ep->pending_type) {
    case MGCP_PEND_AUEP:
        /* Log every header the phone reports back (capabilities, events, signals,
           digit map) — probing the ShoreTel extension-assignment mechanism. */
        for (i = 1; i < num_lines; i++) {
            if (lines[i][0] == '\0') {
                continue;
            }
            if (!strncasecmp(lines[i], "A:", 2)) {
                const char *cap = lines[i] + 2;
                while (*cap == ' ') cap++;
                switch_copy_string(ep->capabilities, cap, sizeof(ep->capabilities));
            }
            switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO,
                              "Phone %s AUEP: %s\n", ep->name, lines[i]);
        }
        ep->pending_type = MGCP_PEND_NONE;
        if (!(code >= 200 && code < 300)) {
            switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_ERROR,
                              "AUEP failed for %s: %d\n", ep->name, code);
        }
        /* Registration complete. EMPIRICAL TEST: create the connection (CRCX)
           now instead of waiting for off-hook — the phone's "Requesting Service"
           clears on the CRCX response, not the AUEP. */
        if (code >= 200 && code < 300) {
            mgcp_send_crcx(ep);
        }
        break;

    case MGCP_PEND_CRCX:
        if (code >= 200 && code < 300) {
            int blank = -1;

            /* Connection-Id (I:) and the SDP body (after the blank line) */
            for (i = 1; i < num_lines; i++) {
                if (!strncasecmp(lines[i], "I:", 2)) {
                    const char *cid = lines[i] + 2;
                    while (*cid == ' ') cid++;
                    switch_copy_string(ep->connection_id, cid, sizeof(ep->connection_id));
                }
                if (blank < 0 && lines[i][0] == '\0') {
                    blank = i;
                }
            }
            if (blank >= 0 && blank + 1 < num_lines) {
                int off = 0;
                for (i = blank + 1; i < num_lines; i++) {
                    off += snprintf(ep->sdp + off, sizeof(ep->sdp) - off, "%s\n", lines[i]);
                }
            }

            ep->has_connection = 1;
            ep->pending_type = MGCP_PEND_NONE;
            switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO,
                              "Phone %s connection established (I: %s)\n", ep->name, ep->connection_id);

            /* Connection is up — arm on-hook/flash/digits and request dial tone
               (dial tone is an RTP stream the phone now has a path to receive). */
            mgcp_send_rqnt(ep, MGCP_OFFHOOK_EVENTS, "L/dl", "Dialing...", "");
        } else {
            switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_ERROR,
                              "CRCX failed for %s: %d\n", ep->name, code);
            ep->pending_type = MGCP_PEND_NONE;
        }
        break;

    case MGCP_PEND_DLCX:
        ep->has_connection = 0;
        ep->connection_id[0] = '\0';
        ep->sdp[0] = '\0';
        ep->pending_type = MGCP_PEND_NONE;
        /* Connection torn down (or already gone, e.g. 515) — return to idle:
           monitor off-hook and clear the LCD. */
        /* Re-arm off-hook monitoring AND audit the endpoint, matching the boot
           registration flow (RQNT -> AUEP). The AUEP appears to reset the phone's
           hook-state machine so the next "hd" latches off-hook correctly; without
           it, a re-pickup gets "402 on-hook". */
        ep->audit_pending = 1;
        mgcp_send_rqnt(ep, "L/hd(N)", mgcp_line_signals(ep), "", "Ready (irl.coop)");
        /* Hangup the FreeSWITCH session if it exists */
        if (ep->session) {
            switch_channel_t *channel = switch_core_session_get_channel(ep->session);
            switch_channel_hangup(channel, SWITCH_CAUSE_NORMAL_CLEARING);
            ep->session = NULL;
        }
        break;

    case MGCP_PEND_RQNT:
        ep->pending_type = MGCP_PEND_NONE;
        if (ep->audit_pending) {
            /* Registration RQNT acked — now audit the endpoint (Asterisk order) */
            ep->audit_pending = 0;
            mgcp_send_auep(ep);
        } else if (code == 402 && !ep->on_hook && !ep->dialtone_retried) {
            /* Phone rejected dial tone as "on-hook" — its off-hook state hadn't
               latched (happens on the pickup after a hangup). Wait and retry once. */
            ep->dialtone_retried = 1;
            switch_sleep(500000);
            mgcp_send_rqnt(ep, MGCP_OFFHOOK_EVENTS, "L/dl", "Dialing...", "");
        }
        break;

    default:
        break;
    }
}

/* Parse and handle a packet */
void mgcp_handle_packet(char *buf, switch_size_t len, switch_sockaddr_t *from_addr)
{
    char *from_ip_ptr;
    switch_port_t from_port;
    char *first_line;
    char *verb, *trans_id, *ep_str;
    char *lines[100];
    int num_lines;
    char reply[256];
    char *version;
    char ep_name[128] = {0};
    char *at;
    mgcp_endpoint_t *ep;
    int i;

    switch_sockaddr_ip_get(&from_ip_ptr, from_addr);
    from_port = switch_sockaddr_get_port(from_addr);

    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "RX from %s:%d\n---\n%s---\n", from_ip_ptr, from_port, buf);

    /* Split into lines */
    num_lines = switch_separate_string(buf, '\n', lines, sizeof(lines) / sizeof(lines[0]));
    if (num_lines == 0) return;

    /* Strip trailing CR from every line */
    for (i = 0; i < num_lines; i++) {
        size_t l = strlen(lines[i]);
        if (l > 0 && lines[i][l - 1] == '\r') {
            lines[i][l - 1] = '\0';
        }
    }

    first_line = lines[0];

    /* Is this a response to our request? (Starts with a 3-digit number) */
    if (isdigit((unsigned char)first_line[0]) && isdigit((unsigned char)first_line[1]) && isdigit((unsigned char)first_line[2])) {
        char code_str[4] = {0};
        char *tid_str;
        int code;

        memcpy(code_str, first_line, 3);
        code = atoi(code_str);
        tid_str = first_line + 3;
        while (*tid_str == ' ') tid_str++;

        ep = mgcp_endpoint_find_by_addr(from_ip_ptr, from_port);
        if (ep) {
            mgcp_handle_response(ep, code, tid_str, lines, num_lines);
        } else {
            switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_WARNING,
                              "Response from unknown endpoint %s:%d: %s\n", from_ip_ptr, from_port, first_line);
        }
        return;
    }

    /* It's a request: VERB TRANS_ID ENDPOINT VERSION */
    verb = first_line;
    trans_id = strchr(verb, ' ');
    if (!trans_id) return;
    *trans_id++ = '\0';

    ep_str = strchr(trans_id, ' ');
    if (!ep_str) return;
    *ep_str++ = '\0';

    version = strchr(ep_str, ' ');
    if (version) *version++ = '\0';

    /* Parse endpoint name (strip the @ip part) */
    at = strchr(ep_str, '@');
    if (at) {
        strncpy(ep_name, ep_str, at - ep_str);
    } else {
        switch_copy_string(ep_name, ep_str, sizeof(ep_name));
    }

    ep = mgcp_endpoint_find_or_create(ep_name, from_ip_ptr, from_port, from_addr);

    if (!strcasecmp(verb, "RSIP")) {
        int is_restart = 0;

        /* Distinguish RM: restart (fresh boot) from RM: disconnected (the
           phone's "disconnected"/"Requesting Service" keepalive). */
        for (i = 1; i < num_lines; i++) {
            if (!strncasecmp(lines[i], "RM: ", 4) && strstr(lines[i], "restart")) {
                is_restart = 1;
                break;
            }
        }

        snprintf(reply, sizeof(reply), "200 %s\n", trans_id);
        mgcp_send_message(ep, reply);

        /* A fresh boot invalidates the endpoint's cached state. */
        if (is_restart) {
            ep->capabilities[0] = '\0';
            ep->has_connection = 0;
            ep->on_hook = 1;
            ep->audit_pending = 0;
            ep->dialtone_retried = 0;
            ep->extension[0] = '\0';
        }

        /* The phone holds its "disconnected" state (LCD "Requesting Service")
           until it receives a *command*. A bare 200 ack is not a command, so it
           stays disconnected and re-RSIPs forever. Re-arm the line appearance +
           audit whenever it RSIPs while on-hook; skip only while off-hook (in a
           call) so we don't reset its hook state mid-dial and get "402 on-hook".
        */
        if (ep->on_hook) {
            char line_signals[128];
            char disp2[64];

            if (ep->extension[0] == '\0') {
                mgcp_resolve_extension(ep);
            }

            snprintf(line_signals, sizeof(line_signals),
                     "KY/ls(1,%s), KY/ks(1,id)", ep->extension);
            snprintf(disp2, sizeof(disp2), "  Extension %s  ", ep->extension);

            ep->audit_pending = 1;
            mgcp_send_rqnt(ep, "L/hd(N)", line_signals, "  irl.coop  ", disp2);
        }
    }
    else if (!strcasecmp(verb, "NTFY")) {
        /* Notification (e.g. phone went off-hook) */

        /* Acknowledge the notification immediately */
        snprintf(reply, sizeof(reply), "200 %s\n", trans_id);
        mgcp_send_message(ep, reply);

        /* Look for the O: (ObservedEvents) header */
        for (i = 1; i < num_lines; i++) {
            if (!strncasecmp(lines[i], "O: ", 3)) {
                if (strstr(lines[i], "hd")) {
                    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "Phone %s went OFF-HOOK (hd)\n", ep->name);
                    ep->on_hook = 0;
                    ep->dialtone_retried = 0;

                    /* Give the phone a moment to latch its off-hook state. A
                       keepalive RSIP firing at the same instant as the pickup
                       leaves the phone briefly "on-hook", and an immediate
                       CRCX + dial-tone RQNT gets "402 on-hook". */
                    switch_sleep(300000);
                    mgcp_send_crcx(ep);
                }
                else if (strstr(lines[i], "hu")) {
                    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "Phone %s went ON-HOOK (hu)\n", ep->name);
                    ep->on_hook = 1;

                    if (ep->has_connection) {
                        /* Tear down the call connection; the DLCX response handler
                           returns us to idle monitoring. */
                        mgcp_send_dlcx(ep);
                    } else {
                        /* No connection to tear down — go straight to idle */
                        /* Re-arm off-hook monitoring AND audit the endpoint, matching the boot
           registration flow (RQNT -> AUEP). The AUEP appears to reset the phone's
           hook-state machine so the next "hd" latches off-hook correctly; without
           it, a re-pickup gets "402 on-hook". */
        ep->audit_pending = 1;
        mgcp_send_rqnt(ep, "L/hd(N)", mgcp_line_signals(ep), "", "Ready (irl.coop)");
                    }
                }
                else if (strstr(lines[i], "d/") || strstr(lines[i], "D/")) {
                    char *dmark;
                    char digit;
                    char disp[128];

                    /* Digit collected. The O: line looks like "u/ku(2), d/2" —
                       grab the character right after "d/" (the digit). */
                    dmark = strstr(lines[i], "d/");
                    if (!dmark) dmark = strstr(lines[i], "D/");
                    digit = dmark[2];
                    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "Phone %s pressed digit: %c\n", ep->name, digit);

                    /* Stop dial tone (empty signal), update screen with digit */
                    snprintf(disp, sizeof(disp), "Dialing: %c...", digit);
                    mgcp_send_rqnt(ep, MGCP_OFFHOOK_EVENTS, "", disp, "");
                }
            }
        }
    }
    else {
        /* Unknown or unhandled verb, just 200 OK it to stop retransmits */
        snprintf(reply, sizeof(reply), "200 %s\n", trans_id);
        mgcp_send_message(ep, reply);
    }
}
