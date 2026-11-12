import esphome.codegen as cg
from esphome.components import text_sensor
import esphome.config_validation as cv

from . import CONF_OBD2_ID, Obd2Component

CONF_VIN = "vin"
CONF_FAULT_CODES = "fault_codes"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_OBD2_ID): cv.use_id(Obd2Component),
        cv.Optional(CONF_VIN): text_sensor.text_sensor_schema(icon="mdi:car-info"),
        cv.Optional(CONF_FAULT_CODES): text_sensor.text_sensor_schema(icon="mdi:engine-off"),
    }
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_OBD2_ID])
    if CONF_VIN in config:
        cg.add(hub.set_vin_sensor(await text_sensor.new_text_sensor(config[CONF_VIN])))
    if CONF_FAULT_CODES in config:
        cg.add(hub.set_dtc_sensor(await text_sensor.new_text_sensor(config[CONF_FAULT_CODES])))
