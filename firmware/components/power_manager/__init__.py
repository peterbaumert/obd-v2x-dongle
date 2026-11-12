"""Parking mode / deep sleep for the dongle.

Modes (decided at every boot / wake and while awake):
  DRIVING   engine running (car battery above `engine_on_voltage`): everything on, never sleeps
  PARKED    engine just stopped: stays awake for `parking_delay`, then shuts down and sleeps
  CHECK     woke from deep sleep: one ADC reading of the car battery, back to sleep at once unless
            the engine runs, the car was unplugged, or a position report is due
  REPORT    report due (`report_interval`, or `low_battery_report_interval` below `low_battery_voltage`,
            or just unplugged): network on until `report_done()` is called or `report_timeout` passes

All thresholds and intervals are Home Assistant number entities (passed in by id), so they can be changed
at runtime. Timing between wakes is kept in RTC memory (survives deep sleep, not power loss).
"""
from esphome import automation
import esphome.codegen as cg
from esphome.components import binary_sensor, deep_sleep, number, switch
from esphome.components.esp32 import include_builtin_idf_component
from esphome.components.adc.sensor import ADCSensor
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_TRIGGER_ID

DEPENDENCIES = ["deep_sleep"]

CONF_DEEP_SLEEP_ID = "deep_sleep_id"
CONF_BATTERY_ADC = "battery_adc"
CONF_VOLTAGE_MULTIPLIER = "voltage_multiplier"
CONF_MODEM_STATUS = "modem_status"
CONF_STAY_AWAKE = "stay_awake"
CONF_ON_NETWORK = "on_network"
CONF_ON_SHUTDOWN = "on_shutdown"
SETTINGS = (
    "engine_on_voltage",
    "unplugged_voltage",
    "low_battery_voltage",
    "parking_delay",
    "check_interval",
    "report_interval",
    "low_battery_report_interval",
    "report_timeout",
)

ns = cg.esphome_ns.namespace("power_manager")
PowerManager = ns.class_("PowerManager", cg.Component)
NetworkTrigger = ns.class_("NetworkTrigger", automation.Trigger.template())
ShutdownTrigger = ns.class_("ShutdownTrigger", automation.Trigger.template())
ReportDoneAction = ns.class_("ReportDoneAction", automation.Action)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(PowerManager),
        cv.GenerateID(CONF_DEEP_SLEEP_ID): cv.use_id(deep_sleep.DeepSleepComponent),
        cv.Required(CONF_BATTERY_ADC): cv.use_id(ADCSensor),
        cv.Optional(CONF_VOLTAGE_MULTIPLIER, default=1.0): cv.positive_float,
        cv.Optional(CONF_MODEM_STATUS): cv.use_id(binary_sensor.BinarySensor),
        cv.Optional(CONF_STAY_AWAKE): cv.use_id(switch.Switch),
        **{cv.Required(k): cv.use_id(number.Number) for k in SETTINGS},
        cv.Optional(CONF_ON_NETWORK): automation.validate_automation(
            {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(NetworkTrigger)}
        ),
        cv.Optional(CONF_ON_SHUTDOWN): automation.validate_automation(
            {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(ShutdownTrigger)}
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    include_builtin_idf_component("esp_driver_usb_serial_jtag")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_deep_sleep(await cg.get_variable(config[CONF_DEEP_SLEEP_ID])))
    cg.add(var.set_battery_adc(await cg.get_variable(config[CONF_BATTERY_ADC])))
    cg.add(var.set_voltage_multiplier(config[CONF_VOLTAGE_MULTIPLIER]))
    if CONF_MODEM_STATUS in config:
        cg.add(var.set_modem_status(await cg.get_variable(config[CONF_MODEM_STATUS])))
    if CONF_STAY_AWAKE in config:
        cg.add(var.set_stay_awake(await cg.get_variable(config[CONF_STAY_AWAKE])))
    for k in SETTINGS:
        cg.add(getattr(var, f"set_{k}")(await cg.get_variable(config[k])))
    for conf in config.get(CONF_ON_NETWORK, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, [], conf)
    for conf in config.get(CONF_ON_SHUTDOWN, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, [], conf)


@automation.register_action(
    "power_manager.report_done",
    ReportDoneAction,
    automation.maybe_simple_id({cv.GenerateID(): cv.use_id(PowerManager)}),
    synchronous=True,
)
async def report_done_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    return var
