"""Second MQTT connection for the OpenTrafficMap C-ITS server.

ESPHome's `mqtt:` component holds one broker connection, which this firmware uses for the owner's broker
(Home Assistant discovery). This component opens an independent esp-mqtt client to OpenTrafficMap and
publishes the received ITS-G5 frames like the reference receiver firmware:

    its/<node_id>/packet   raw frame bytes
    its/<node_id>/status   "online" (retained) / last will "offline"
    its/<node_id>/info     {"ver": ..., "hwv": "obd-v2x-dongle"} once per connection
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_PORT

CODEOWNERS = []
DEPENDENCIES = ["mqtt", "network"]

CONF_BROKER = "broker"
CONF_NODE_ID = "node_id"

otm_ns = cg.esphome_ns.namespace("otm_uplink")
OtmUplink = otm_ns.class_("OtmUplink", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(OtmUplink),
        cv.Required(CONF_NODE_ID): cv.All(cv.string_strict, cv.Length(min=1, max=40)),
        cv.Optional(CONF_BROKER, default="cits1.opentrafficmap.org"): cv.domain,
        cv.Optional(CONF_PORT, default=8883): cv.port,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_node_id(config[CONF_NODE_ID]))
    cg.add(var.set_broker(config[CONF_BROKER], config[CONF_PORT]))
