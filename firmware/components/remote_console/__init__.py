"""Remote console: a line-based TCP prompt for diagnostics over the WireGuard tunnel.

Not SSH: the tunnel already encrypts and authenticates, so this is plain text on a TCP port that is only open
while `set_enabled(true)` (a Home Assistant switch) and only answers on `listen_address` (the dongle's tunnel
address; connections arriving on any other interface, e.g. the mobile network, are closed at once).
Connect with `nc <tunnel address> 2323` or PuTTY (connection type "Raw"). One session at a time.

Commands: `help`, `status`, `log on|off|error|warn|info|debug` (live log), `obd [7Ex] <hex bytes>` (one read-only
diagnostic request, see obd2's raw_request), `at <command>` or just `AT...` (modem), `reboot`, `exit`.
"""
import esphome.codegen as cg
from esphome.components import logger
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_PASSWORD, CONF_PORT

DEPENDENCIES = ["esp32", "logger", "network"]

CONF_LISTEN_ADDRESS = "listen_address"
CONF_IDLE_TIMEOUT = "idle_timeout"
CONF_OBD2_ID = "obd2_id"
CONF_MODEM_ID = "modem_id"
CONF_STATUS = "status"

ns = cg.esphome_ns.namespace("remote_console")
RemoteConsole = ns.class_("RemoteConsole", cg.Component)
Obd2Component = cg.esphome_ns.namespace("obd2").class_("Obd2Component", cg.Component)
ModemComponent = cg.esphome_ns.namespace("modem").class_("ModemComponent", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(RemoteConsole),
        cv.Required(CONF_LISTEN_ADDRESS): cv.ipv4address,
        cv.Optional(CONF_PORT, default=2323): cv.port,
        cv.Optional(CONF_PASSWORD): cv.All(cv.string_strict, cv.Length(min=1, max=63)),
        cv.Optional(CONF_IDLE_TIMEOUT, default="10min"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_OBD2_ID): cv.use_id(Obd2Component),
        cv.Optional(CONF_MODEM_ID): cv.use_id(ModemComponent),
        # Extra lines for `status` (returns std::string)
        cv.Optional(CONF_STATUS): cv.returning_lambda,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    logger.request_log_listener()
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_listen_address(str(config[CONF_LISTEN_ADDRESS])))
    cg.add(var.set_port(config[CONF_PORT]))
    cg.add(var.set_idle_timeout(config[CONF_IDLE_TIMEOUT]))
    if CONF_PASSWORD in config:
        cg.add(var.set_password(config[CONF_PASSWORD]))
    if CONF_OBD2_ID in config:
        cg.add_define("USE_REMOTE_CONSOLE_OBD2")
        cg.add(var.set_obd2(await cg.get_variable(config[CONF_OBD2_ID])))
    if CONF_MODEM_ID in config:
        cg.add_define("USE_REMOTE_CONSOLE_MODEM")
        cg.add_define("USE_MODEM_SEND_AT")
        cg.add(var.set_modem(await cg.get_variable(config[CONF_MODEM_ID])))
    if CONF_STATUS in config:
        status = await cg.process_lambda(config[CONF_STATUS], [], return_type=cg.std_string)
        cg.add(var.set_status(status))
