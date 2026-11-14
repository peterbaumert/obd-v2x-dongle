"""OBD-II over CAN (ISO 15765-4, 11-bit IDs) on ESP-IDF's TWAI node driver.

ESPHome's esp32_can uses ESP-IDF's legacy TWAI driver, which is not built for CAN-FD capable chips such as
the ESP32-C5, so this component talks to the new driver (esp_twai_onchip) directly.

The node only runs while `set_active(true)` (e.g. engine running): otherwise the CAN controller is disabled
and the transceiver held in standby, so a parked car's bus is never woken. While active it sends one
mode 01 request every `poll_interval` (round robin over the configured sensors) to the functional address
0x7DF and decodes the responses from 0x7E8..0x7EF. Multi-frame responses (ISO-TP: VIN, long fault code lists)
are reassembled per ECU (flow control to 0x7E0..0x7E7). It also reads the VIN once, the stored fault codes
(mode 03) on activation and every `dtc_interval`, and clears them (mode 04) from a button.

Vehicle profiles (profiles.py): the broadcast frames listed in the active profile are decoded passively, nothing is
sent for them. After the engine stops the node keeps listening (receive only, no requests) for
`listen_after_stop`, so doors and the lock state are still seen when the driver leaves.
"""
from esphome import pins
import esphome.codegen as cg
from esphome.components.esp32 import include_builtin_idf_component
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_RX_PIN, CONF_TX_PIN

from .profiles import KIND_ENUM, KIND_FLAG, KIND_NUMBER, load_profiles, signal_catalog, signal_index

DEPENDENCIES = ["esp32"]
AUTO_LOAD = ["sensor", "binary_sensor", "text_sensor", "button", "select"]

CONF_BIT_RATE = "bit_rate"
CONF_STANDBY_PIN = "standby_pin"
CONF_POLL_INTERVAL = "poll_interval"
CONF_DTC_INTERVAL = "dtc_interval"
CONF_LISTEN_AFTER_STOP = "listen_after_stop"
CONF_SIGNAL_INTERVAL = "signal_interval"
CONF_OBD2_ID = "obd2_id"

obd2_ns = cg.esphome_ns.namespace("obd2")
Obd2Component = obd2_ns.class_("Obd2Component", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(Obd2Component),
        cv.Required(CONF_TX_PIN): pins.internal_gpio_output_pin_number,
        cv.Required(CONF_RX_PIN): pins.internal_gpio_input_pin_number,
        cv.Optional(CONF_STANDBY_PIN): pins.gpio_output_pin_schema,
        cv.Optional(CONF_BIT_RATE, default=500000): cv.one_of(250000, 500000, int=True),
        cv.Optional(CONF_POLL_INTERVAL, default="250ms"): cv.All(
            cv.positive_time_period_milliseconds,
            cv.Range(min=cv.TimePeriod(milliseconds=50)),
        ),
        cv.Optional(CONF_DTC_INTERVAL, default="5min"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_LISTEN_AFTER_STOP, default="3min"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_SIGNAL_INTERVAL, default="1s"): cv.positive_time_period_milliseconds,
    }
).extend(cv.COMPONENT_SCHEMA)


def _add_profiles(var):
    """Compile every profile into the component: add_profile, then its signal definitions."""
    cg.add(var.set_signal_count(len(signal_catalog())))
    for p in load_profiles():
        cg.add(var.add_profile(p.title))
        for s in p.signals:
            idx = signal_index(s.name)
            if s.kind == KIND_NUMBER:
                cg.add(var.add_number(idx, s.can_id, s.start, s.length, s.little, s.scale, s.offset))
            elif s.kind == KIND_FLAG:
                cg.add(var.add_flag(idx, s.can_id, s.start, s.mask))
            elif s.kind == KIND_ENUM:
                cg.add(var.add_enum(idx, s.can_id, s.start, s.length, s.little, s.mask))
                for raw, state in s.values:
                    cg.add(var.add_enum_value(raw, state, state == s.on))
            for raw in s.invalid:
                cg.add(var.add_invalid(raw))


async def to_code(config):
    include_builtin_idf_component("esp_driver_twai")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_pins(config[CONF_TX_PIN], config[CONF_RX_PIN]))
    cg.add(var.set_bit_rate(config[CONF_BIT_RATE]))
    cg.add(var.set_poll_interval(config[CONF_POLL_INTERVAL]))
    cg.add(var.set_dtc_interval(config[CONF_DTC_INTERVAL]))
    cg.add(var.set_listen_after_stop(config[CONF_LISTEN_AFTER_STOP]))
    cg.add(var.set_signal_interval(config[CONF_SIGNAL_INTERVAL]))
    _add_profiles(var)
    if CONF_STANDBY_PIN in config:
        pin = await cg.gpio_pin_expression(config[CONF_STANDBY_PIN])
        cg.add(var.set_standby_pin(pin))
