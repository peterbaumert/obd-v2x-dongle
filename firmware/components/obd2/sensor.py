import esphome.codegen as cg
from esphome.components import sensor
import esphome.config_validation as cv
from esphome.const import (
    DEVICE_CLASS_SPEED,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    STATE_CLASS_MEASUREMENT,
    UNIT_CELSIUS,
    UNIT_PERCENT,
    UNIT_VOLT,
)

from . import CONF_OBD2_ID, Obd2Component

# config key -> (mode 01 PID, unit, device class, icon, decimals)
PIDS = {
    "engine_load": (0x04, UNIT_PERCENT, None, "mdi:gauge", 0),
    "coolant_temperature": (0x05, UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, None, 0),
    "rpm": (0x0C, "rpm", None, "mdi:engine", 0),
    "speed": (0x0D, "km/h", DEVICE_CLASS_SPEED, None, 0),
    "intake_temperature": (0x0F, UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, None, 0),
    "fuel_level": (0x2F, UNIT_PERCENT, None, "mdi:gas-station", 0),
    "ecu_voltage": (0x42, UNIT_VOLT, DEVICE_CLASS_VOLTAGE, None, 2),
    "ambient_temperature": (0x46, UNIT_CELSIUS, DEVICE_CLASS_TEMPERATURE, None, 0),
}
FAST = {"speed", "rpm"}   # polled twice as often


def _schema(unit, device_class, icon, decimals):
    kw = {"unit_of_measurement": unit, "accuracy_decimals": decimals, "state_class": STATE_CLASS_MEASUREMENT}
    if device_class:
        kw["device_class"] = device_class
    if icon:
        kw["icon"] = icon
    return sensor.sensor_schema(**kw)


CONFIG_SCHEMA = cv.Schema(
    {cv.GenerateID(CONF_OBD2_ID): cv.use_id(Obd2Component)}
    | {cv.Optional(k): _schema(*v[1:]) for k, v in PIDS.items()}
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_OBD2_ID])
    for key, (pid, *_rest) in PIDS.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(hub.add_pid(pid, sens, key in FAST))
