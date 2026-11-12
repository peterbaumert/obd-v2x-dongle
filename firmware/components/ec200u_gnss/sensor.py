import esphome.codegen as cg
from esphome.components import sensor
import esphome.config_validation as cv
from esphome.const import (
    CONF_ALTITUDE,
    CONF_COURSE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SATELLITES,
    CONF_SPEED,
    DEVICE_CLASS_DISTANCE,
    DEVICE_CLASS_SPEED,
    STATE_CLASS_MEASUREMENT,
    UNIT_DEGREES,
    UNIT_KILOMETER_PER_HOUR,
    UNIT_METER,
)

from . import CONF_EC200U_GNSS_ID, Ec200uGnss

CONF_HDOP = "hdop"

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_EC200U_GNSS_ID): cv.use_id(Ec200uGnss),
        cv.Optional(CONF_LATITUDE): sensor.sensor_schema(
            unit_of_measurement=UNIT_DEGREES, accuracy_decimals=6, icon="mdi:latitude"
        ),
        cv.Optional(CONF_LONGITUDE): sensor.sensor_schema(
            unit_of_measurement=UNIT_DEGREES, accuracy_decimals=6, icon="mdi:longitude"
        ),
        cv.Optional(CONF_ALTITUDE): sensor.sensor_schema(
            unit_of_measurement=UNIT_METER, accuracy_decimals=1, device_class=DEVICE_CLASS_DISTANCE,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_SPEED): sensor.sensor_schema(
            unit_of_measurement=UNIT_KILOMETER_PER_HOUR, accuracy_decimals=1, device_class=DEVICE_CLASS_SPEED,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        cv.Optional(CONF_COURSE): sensor.sensor_schema(
            unit_of_measurement=UNIT_DEGREES, accuracy_decimals=0, icon="mdi:compass"
        ),
        cv.Optional(CONF_HDOP): sensor.sensor_schema(accuracy_decimals=1, icon="mdi:crosshairs-gps"),
        cv.Optional(CONF_SATELLITES): sensor.sensor_schema(
            accuracy_decimals=0, icon="mdi:satellite-variant", state_class=STATE_CLASS_MEASUREMENT
        ),
    }
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_EC200U_GNSS_ID])
    for key in (CONF_LATITUDE, CONF_LONGITUDE, CONF_ALTITUDE, CONF_SPEED, CONF_COURSE, CONF_HDOP, CONF_SATELLITES):
        if key in config:
            sens = await sensor.new_sensor(config[key])
            cg.add(getattr(hub, f"set_{key}_sensor")(sens))
