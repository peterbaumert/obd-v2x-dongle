import esphome.codegen as cg
from esphome.components import binary_sensor
import esphome.config_validation as cv

from . import CONF_OBD2_ID, Obd2Component
from .profiles import KIND_ENUM, KIND_FLAG, signal_index, signals_validator

CONF_SIGNALS = "signals"
SIGNAL_DEFAULTS = {
    "door_driver_open": dict(device_class="door"),
    "door_passenger_open": dict(device_class="door"),
    "door_rear_left_open": dict(device_class="door"),
    "door_rear_right_open": dict(device_class="door"),
    "boot_open": dict(device_class="opening", icon="mdi:car-back"),
    "interior_light": dict(device_class="light"),
    "locked": dict(icon="mdi:car-key"),
    "driver_seatbelt": dict(icon="mdi:seatbelt"),
    "passenger_seatbelt": dict(icon="mdi:seatbelt"),
    "brake_pedal": dict(icon="mdi:car-brake-alert"),
    "reverse_gear": dict(icon="mdi:car-shift-pattern"),
    "eco_start_stop": dict(icon="mdi:engine-off-outline"),
    "fog_light_button": dict(icon="mdi:car-light-fog"),
    "parking_brake": dict(icon="mdi:car-brake-parking"),
    "ac_on": dict(icon="mdi:air-conditioner"),
}


def _allowed(sig):
    return sig.kind == KIND_FLAG or (sig.kind == KIND_ENUM and sig.on is not None)


def _signal_schema(name, sig):
    return binary_sensor.binary_sensor_schema(**SIGNAL_DEFAULTS.get(name, {}))


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_OBD2_ID): cv.use_id(Obd2Component),
        cv.Optional(CONF_SIGNALS): signals_validator("binary_sensor", _allowed, _signal_schema),
    }
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_OBD2_ID])
    for name, conf in config.get(CONF_SIGNALS, {}).items():
        cg.add(hub.set_signal_binary_sensor(signal_index(name), await binary_sensor.new_binary_sensor(conf)))
