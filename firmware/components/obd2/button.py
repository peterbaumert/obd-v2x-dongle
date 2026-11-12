import esphome.codegen as cg
from esphome.components import button
import esphome.config_validation as cv

from . import CONF_OBD2_ID, Obd2Component, obd2_ns

ClearDtcButton = obd2_ns.class_("ClearDtcButton", button.Button)

CONF_CLEAR_FAULT_CODES = "clear_fault_codes"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_OBD2_ID): cv.use_id(Obd2Component),
        cv.Optional(CONF_CLEAR_FAULT_CODES): button.button_schema(ClearDtcButton, icon="mdi:broom"),
    }
)


async def to_code(config):
    if CONF_CLEAR_FAULT_CODES in config:
        b = await button.new_button(config[CONF_CLEAR_FAULT_CODES])
        await cg.register_parented(b, config[CONF_OBD2_ID])
