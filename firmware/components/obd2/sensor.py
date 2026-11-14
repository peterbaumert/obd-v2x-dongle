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
from .profiles import KIND_NUMBER, UNITS, CONF_RESTORE, signal_index, signals_validator

CONF_SIGNALS = "signals"
# defaults for well-known profile signals; anything else gets the unit from the profile
SIGNAL_DEFAULTS = {
    "odometer": dict(unit_of_measurement="km", device_class="distance", state_class="total_increasing",
                     icon="mdi:counter", accuracy_decimals=1),
    "range": dict(unit_of_measurement="km", device_class="distance", icon="mdi:gas-station-outline",
                  accuracy_decimals=0),
    "fuel_level": dict(unit_of_measurement=UNIT_PERCENT, icon="mdi:gas-station", accuracy_decimals=0),
    "outside_temperature": dict(unit_of_measurement=UNIT_CELSIUS, device_class=DEVICE_CLASS_TEMPERATURE,
                                accuracy_decimals=1),
    "battery_voltage": dict(unit_of_measurement=UNIT_VOLT, device_class=DEVICE_CLASS_VOLTAGE, accuracy_decimals=1),
} | {
    f"tyre_pressure_{pos}": dict(unit_of_measurement="kPa", device_class="pressure", icon="mdi:car-tire-alert",
                                 accuracy_decimals=1)
    for pos in ("front_left", "front_right", "rear_left", "rear_right")
}


def _signal_schema(name, sig):
    kw = {"state_class": STATE_CLASS_MEASUREMENT, "accuracy_decimals": 1}
    if sig.unit:
        kw["unit_of_measurement"] = UNITS.get(sig.unit, sig.unit)
    kw.update(SIGNAL_DEFAULTS.get(name, {}))
    return sensor.sensor_schema(**kw)

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
CONF_DTC_COUNT = "dtc_count"


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
    | {cv.Optional(CONF_DTC_COUNT): sensor.sensor_schema(icon="mdi:engine-off", accuracy_decimals=0)}
    | {cv.Optional(CONF_SIGNALS): signals_validator("sensor", lambda s: s.kind == KIND_NUMBER, _signal_schema)}
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_OBD2_ID])
    for key, (pid, *_rest) in PIDS.items():
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(hub.add_pid(pid, sens, key in FAST))
    if CONF_DTC_COUNT in config:
        cg.add(hub.set_dtc_count_sensor(await sensor.new_sensor(config[CONF_DTC_COUNT])))
    for name, conf in config.get(CONF_SIGNALS, {}).items():
        cg.add(hub.set_signal_sensor(signal_index(name), await sensor.new_sensor(conf)))
        if conf[CONF_RESTORE]:
            cg.add(hub.set_signal_restore(signal_index(name)))
