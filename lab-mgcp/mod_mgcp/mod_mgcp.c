#include "mgcp_protocol.h"
#include "mgcp_endpoint.c"
#include "mgcp_protocol.c"

SWITCH_MODULE_LOAD_FUNCTION(mod_mgcp_load);
SWITCH_MODULE_SHUTDOWN_FUNCTION(mod_mgcp_shutdown);
SWITCH_MODULE_DEFINITION(mod_mgcp, mod_mgcp_load, mod_mgcp_shutdown, NULL);

SWITCH_MODULE_LOAD_FUNCTION(mod_mgcp_load)
{
    switch_endpoint_interface_t *endpoint_interface;

    *module_interface = switch_loadable_module_create_module_interface(pool, modname);

    endpoint_interface = switch_loadable_module_create_interface(*module_interface, SWITCH_ENDPOINT_INTERFACE);
    endpoint_interface->interface_name = "mgcp";
    endpoint_interface->io_routines = &mgcp_io_routines;
    endpoint_interface->state_handler = &mgcp_state_handlers;

    if (mgcp_protocol_init(pool, endpoint_interface) != SWITCH_STATUS_SUCCESS) {
        return SWITCH_STATUS_FALSE;
    }

    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_NOTICE, "mod_mgcp loaded, listening on UDP %d.\n", MGCP_SERVER_PORT);
    return SWITCH_STATUS_SUCCESS;
}

SWITCH_MODULE_SHUTDOWN_FUNCTION(mod_mgcp_shutdown)
{
    mgcp_protocol_destroy();
    switch_log_printf(SWITCH_CHANNEL_LOG, SWITCH_LOG_NOTICE, "mod_mgcp shutting down.\n");
    return SWITCH_STATUS_SUCCESS;
}

