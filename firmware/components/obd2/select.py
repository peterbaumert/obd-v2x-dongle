"""Vehicle profile select: "None" plus every compiled profile; the choice is stored in flash."""
import esphome.codegen as cg
from esphome.components import select
import esphome.config_validation as cv
from esphome.const import ENTITY_CATEGORY_CONFIG

from . import CONF_OBD2_ID, Obd2Component, obd2_ns
from .profiles import load_profiles

VehicleProfileSelect = obd2_ns.class_("VehicleProfileSelect", select.Select, cg.Component)

CONF_VEHICLE_PROFILE = "vehicle_profile"
CONF_INITIAL_PROFILE = "initial_profile"
NONE_ID, NONE_TITLE = "none", "None (OBD only)"


def _validate_initial(value):
    ids = [NONE_ID] + [p.id for p in load_profiles()]
    if value not in ids:
        raise cv.Invalid(f"unknown profile '{value}', available: {', '.join(ids)}")
    return value


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_OBD2_ID): cv.use_id(Obd2Component),
        cv.Optional(CONF_VEHICLE_PROFILE): select.select_schema(
            VehicleProfileSelect, entity_category=ENTITY_CATEGORY_CONFIG, icon="mdi:car-cog"
        )
        .extend({cv.Optional(CONF_INITIAL_PROFILE, default=NONE_ID): cv.All(cv.string, _validate_initial)})
        .extend(cv.COMPONENT_SCHEMA),
    }
)


async def to_code(config):
    if CONF_VEHICLE_PROFILE not in config:
        return
    conf = config[CONF_VEHICLE_PROFILE]
    profiles = load_profiles()
    var = await select.new_select(conf, options=[NONE_TITLE] + [p.title for p in profiles])
    await cg.register_component(var, conf)
    await cg.register_parented(var, config[CONF_OBD2_ID])
    ids = [NONE_ID] + [p.id for p in profiles]
    cg.add(var.set_initial_index(ids.index(conf[CONF_INITIAL_PROFILE])))
