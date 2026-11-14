import esphome.codegen as cg
from esphome.components import text_sensor
import esphome.config_validation as cv

from . import CONF_OBD2_ID, Obd2Component
from .profiles import KIND_ENUM, CONF_RESTORE, signal_index, signals_validator

CONF_VIN = "vin"
CONF_FAULT_CODES = "fault_codes"
CONF_SIGNALS = "signals"
SIGNAL_ICONS = {"light_switch": "mdi:car-light-dimmed", "locked": "mdi:car-key", "parking_brake": "mdi:car-brake-parking"}


def _signal_schema(name, sig):
    return text_sensor.text_sensor_schema(icon=SIGNAL_ICONS.get(name, "mdi:car-info"))

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_OBD2_ID): cv.use_id(Obd2Component),
        cv.Optional(CONF_VIN): text_sensor.text_sensor_schema(icon="mdi:car-info"),
        cv.Optional(CONF_FAULT_CODES): text_sensor.text_sensor_schema(icon="mdi:engine-off"),
        cv.Optional(CONF_SIGNALS): signals_validator("text_sensor", lambda s: s.kind == KIND_ENUM, _signal_schema),
    }
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_OBD2_ID])
    if CONF_VIN in config:
        cg.add(hub.set_vin_sensor(await text_sensor.new_text_sensor(config[CONF_VIN])))
    if CONF_FAULT_CODES in config:
        cg.add(hub.set_dtc_sensor(await text_sensor.new_text_sensor(config[CONF_FAULT_CODES])))
    for name, conf in config.get(CONF_SIGNALS, {}).items():
        cg.add(hub.set_signal_text_sensor(signal_index(name), await text_sensor.new_text_sensor(conf)))
        if conf[CONF_RESTORE]:
            cg.add(hub.set_signal_restore(signal_index(name)))
