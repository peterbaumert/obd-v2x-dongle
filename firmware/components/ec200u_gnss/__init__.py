"""GNSS position from the Quectel EC200U's built-in receiver, read over the modem's AT channel.

ESPHome's modem component (PPP + CMUX) can send AT commands while the data connection runs
(`send_at`), but it only logs the reply. This component sends `AT+QGPSLOC=2` every `update_interval`
and picks the answer out of that log line through a logger listener, so it works with the stock
modem component. It starts the receiver (`AT+QGPS=1`) once the modem is connected and again whenever
the modem reports that the GNSS session is not active (+CME ERROR: 505).
"""
import esphome.codegen as cg
from esphome.components import logger
from esphome.components.modem import CONF_MODEM_ID, ModemComponent
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["modem", "logger"]
MULTI_CONF = False

CONF_EC200U_GNSS_ID = "ec200u_gnss_id"

ns = cg.esphome_ns.namespace("ec200u_gnss")
Ec200uGnss = ns.class_("Ec200uGnss", cg.PollingComponent)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(Ec200uGnss),
        cv.GenerateID(CONF_MODEM_ID): cv.use_id(ModemComponent),
    }
).extend(cv.polling_component_schema("10s"))


async def to_code(config):
    cg.add_define("USE_MODEM_SEND_AT")
    logger.request_log_listener()
    modem = await cg.get_variable(config[CONF_MODEM_ID])
    var = cg.new_Pvariable(config[CONF_ID], modem)
    await cg.register_component(var, config)
