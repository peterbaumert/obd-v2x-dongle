#pragma once

#include <atomic>
#include <string>
#include <vector>

#include <mqtt_client.h>

#include "esphome/core/component.h"

namespace esphome::otm_uplink {

/// Independent esp-mqtt client (TLS, port 8883) to the OpenTrafficMap C-ITS server.
class OtmUplink : public Component {
 public:
  void set_node_id(const std::string &node_id) { this->node_id_ = node_id; }
  void set_broker(const std::string &host, uint16_t port) {
    this->host_ = host;
    this->port_ = port;
  }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_CONNECTION; }

  /// Publish one raw ITS-G5 frame to its/<node_id>/packet (dropped while disconnected).
  void publish_packet(const std::vector<uint8_t> &frame);
  bool is_connected() const { return this->connected_.load(); }
  uint32_t get_published() const { return this->published_.load(); }

 protected:
  static void event_handler_(void *arg, esp_event_base_t base, int32_t event_id, void *event_data);

  std::string node_id_;
  std::string host_;
  uint16_t port_{8883};
  std::string uri_;
  std::string topic_packet_;
  std::string topic_status_;
  std::string topic_info_;
  esp_mqtt_client_handle_t client_{nullptr};
  bool started_{false};
  std::atomic<bool> connected_{false};
  std::atomic<uint32_t> published_{0};
};

}  // namespace esphome::otm_uplink
