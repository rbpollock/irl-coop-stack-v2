#include "mgcp_protocol.h"

/* Basic State Handlers */
static switch_status_t mgcp_on_init(switch_core_session_t *session)
{
    switch_channel_t *channel = switch_core_session_get_channel(session);
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "%s mgcp_on_init\n", switch_channel_get_name(channel));
    switch_channel_set_state(channel, CS_ROUTING);
    return SWITCH_STATUS_SUCCESS;
}

static switch_status_t mgcp_on_routing(switch_core_session_t *session)
{
    switch_channel_t *channel = switch_core_session_get_channel(session);
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "%s mgcp_on_routing\n", switch_channel_get_name(channel));
    return SWITCH_STATUS_SUCCESS;
}

static switch_status_t mgcp_on_execute(switch_core_session_t *session)
{
    switch_channel_t *channel = switch_core_session_get_channel(session);
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "%s mgcp_on_execute\n", switch_channel_get_name(channel));
    return SWITCH_STATUS_SUCCESS;
}

static switch_status_t mgcp_on_hangup(switch_core_session_t *session)
{
    switch_channel_t *channel = switch_core_session_get_channel(session);
    mgcp_endpoint_t *ep = switch_channel_get_private(channel, "mgcp_ep");
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "%s mgcp_on_hangup\n", switch_channel_get_name(channel));
    
    if (ep) {
        ep->session = NULL;
    }
    return SWITCH_STATUS_SUCCESS;
}

static switch_status_t mgcp_on_destroy(switch_core_session_t *session)
{
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_INFO, "mgcp_on_destroy\n");
    return SWITCH_STATUS_SUCCESS;
}

switch_state_handler_table_t mgcp_state_handlers = {
    .on_init = mgcp_on_init,
    .on_routing = mgcp_on_routing,
    .on_execute = mgcp_on_execute,
    .on_hangup = mgcp_on_hangup,
    .on_destroy = mgcp_on_destroy
};

/* IO Routines */
static switch_call_cause_t mgcp_outgoing_channel(switch_core_session_t *session, switch_event_t *var_event,
                                                 switch_caller_profile_t *outbound_profile,
                                                 switch_core_session_t **new_session, switch_memory_pool_t **pool,
                                                 switch_originate_flag_t flags, switch_call_cause_t *cancel_cause)
{
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_ERROR, "Outgoing calls to MGCP not implemented yet!\n");
    return SWITCH_CAUSE_DESTINATION_OUT_OF_ORDER;
}

switch_io_routines_t mgcp_io_routines = {
    .outgoing_channel = mgcp_outgoing_channel
};
