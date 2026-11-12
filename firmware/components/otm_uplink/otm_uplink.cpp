#include "otm_uplink.h"

#include "esphome/components/network/util.h"
#include "esphome/core/log.h"
#include "esphome/core/version.h"

namespace esphome::otm_uplink {

static const char *const TAG = "otm_uplink";

// The OpenTrafficMap server uses a Let's Encrypt certificate: verify against ISRG Root X1.
static const char ISRG_ROOT_X1[] =
    "-----BEGIN CERTIFICATE-----\n"
    "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\n"
    "-----END CERTIFICATE-----\n";

void OtmUplink::setup() {
  this->uri_ = "mqtts://" + this->host_ + ":" + std::to_string(this->port_);
  const std::string base = "its/" + this->node_id_;
  this->topic_packet_ = base + "/packet";
  this->topic_status_ = base + "/status";
  this->topic_info_ = base + "/info";

  esp_mqtt_client_config_t cfg{};
  cfg.broker.address.uri = this->uri_.c_str();
  cfg.broker.verification.certificate = ISRG_ROOT_X1;
  // The wildcard certificate's hostname check fails with mbedTLS (same as the reference config)
  cfg.broker.verification.skip_cert_common_name_check = true;
  cfg.session.last_will.topic = this->topic_status_.c_str();
  cfg.session.last_will.msg = "offline";
  cfg.session.last_will.msg_len = 7;
  cfg.session.last_will.retain = 1;
  cfg.session.keepalive = 60;
  cfg.network.reconnect_timeout_ms = 10000;
  this->client_ = esp_mqtt_client_init(&cfg);
  if (this->client_ == nullptr) {
    this->mark_failed();
    return;
  }
  esp_mqtt_client_register_event(this->client_, MQTT_EVENT_ANY, &OtmUplink::event_handler_, this);
}

void OtmUplink::loop() {
  // Start once the uplink (LTE / PPP) has an IP; esp-mqtt reconnects on its own after that
  if (!this->started_ && network::is_connected()) {
    if (esp_mqtt_client_start(this->client_) == ESP_OK)
      this->started_ = true;
  }
}

void OtmUplink::event_handler_(void *arg, esp_event_base_t base, int32_t event_id, void *event_data) {
  auto *self = static_cast<OtmUplink *>(arg);
  switch (static_cast<esp_mqtt_event_id_t>(event_id)) {
    case MQTT_EVENT_CONNECTED: {
      self->connected_ = true;
      esp_mqtt_client_publish(self->client_, self->topic_status_.c_str(), "online", 6, 0, 1);
      std::string info = std::string("{\"ver\":\"") + ESPHOME_VERSION + "\",\"hwv\":\"obd-v2x-dongle\"}";
      esp_mqtt_client_publish(self->client_, self->topic_info_.c_str(), info.data(), info.size(), 0, 0);
      ESP_LOGI(TAG, "Connected to %s", self->host_.c_str());
      break;
    }
    case MQTT_EVENT_DISCONNECTED:
      if (self->connected_.exchange(false))
        ESP_LOGW(TAG, "Disconnected");
      break;
    default:
      break;
  }
}

void OtmUplink::publish_packet(const std::vector<uint8_t> &frame) {
  if (!this->connected_ || frame.empty())
    return;
  // Non-blocking: queued in the esp-mqtt outbox, sent by its own task. Frames that arrive faster than the link
  // sends them would grow the outbox without limit, so drop new ones while it is full.
  if (esp_mqtt_client_get_outbox_size(this->client_) > MAX_OUTBOX) {
    this->dropped_++;
    return;
  }
  if (esp_mqtt_client_enqueue(this->client_, this->topic_packet_.c_str(), reinterpret_cast<const char *>(frame.data()),
                              frame.size(), 0, 0, false) >= 0) {
    this->published_++;
    this->bytes_ += frame.size() + this->topic_packet_.size();
  }
}

void OtmUplink::dump_config() {
  ESP_LOGCONFIG(TAG,
                "OpenTrafficMap uplink:\n"
                "  Broker: %s\n"
                "  Node ID: %s",
                this->uri_.c_str(), this->node_id_.c_str());
}

}  // namespace esphome::otm_uplink
