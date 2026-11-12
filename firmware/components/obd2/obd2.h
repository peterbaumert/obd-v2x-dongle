#pragma once

#include <atomic>
#include <string>
#include <vector>

#include <esp_twai.h>
#include <esp_twai_onchip.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

#include "esphome/components/button/button.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"

namespace esphome::obd2 {

struct RxFrame {
  uint32_t id;
  uint8_t len;
  uint8_t data[8];
};

/// OBD-II over CAN (ISO 15765-4, 11-bit) on the TWAI node driver: mode 01 live data, VIN (09/02),
/// stored fault codes (03) and clearing them (04). Multi-frame (ISO-TP) responses are reassembled per ECU.
class Obd2Component : public Component {
 public:
  void set_pins(int tx, int rx) {
    this->tx_pin_ = tx;
    this->rx_pin_ = rx;
  }
  void set_bit_rate(uint32_t bit_rate) { this->bit_rate_ = bit_rate; }
  void set_poll_interval(uint32_t ms) { this->poll_interval_ = ms; }
  void set_dtc_interval(uint32_t ms) { this->dtc_interval_ = ms; }
  void set_standby_pin(GPIOPin *pin) { this->standby_pin_ = pin; }
  void add_pid(uint8_t pid, sensor::Sensor *sens, bool fast);
  void set_vin_sensor(text_sensor::TextSensor *s) { this->vin_sensor_ = s; }
  void set_dtc_sensor(text_sensor::TextSensor *s) { this->dtc_sensor_ = s; }
  void set_dtc_count_sensor(sensor::Sensor *s) { this->dtc_count_sensor_ = s; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }

  /// Start (true) or stop (false) talking on the bus; stopped = controller off, transceiver in standby.
  void set_active(bool active);
  bool is_active() const { return this->active_; }
  /// Mode 04: clear stored fault codes (only while active), then read them again.
  void clear_dtcs();

 protected:
  static constexpr size_t MAX_MSG = 128;
  static constexpr uint8_t NUM_ECUS = 8;  // 0x7E8..0x7EF
  static constexpr uint8_t TX_SLOTS = 4;

  enum class Pending : uint8_t { NONE, VIN, DTC, CLEAR };

  struct IsoTpRx {
    bool busy{false};
    uint16_t len{0};
    uint16_t got{0};
    uint8_t next_sn{0};
    uint8_t buf[MAX_MSG];
  };

  struct Pid {
    uint8_t pid;
    sensor::Sensor *sensor;
  };

  static bool on_rx_(twai_node_handle_t node, const twai_rx_done_event_data_t *edata, void *ctx);
  static bool on_tx_done_(twai_node_handle_t node, const twai_tx_done_event_data_t *edata, void *ctx);
  static bool on_state_(twai_node_handle_t node, const twai_state_change_event_data_t *edata, void *ctx);
  bool send_(uint32_t id, const uint8_t *data, uint8_t len);
  bool request_(const uint8_t *payload, uint8_t len);
  void handle_frame_(const RxFrame &frame);
  void handle_message_(uint8_t ecu, const uint8_t *d, uint16_t n);
  void handle_pid_(const uint8_t *d, uint16_t n);
  void finish_pending_();
  void poll_pid_();

  std::vector<Pid> pids_;
  std::vector<uint8_t> schedule_;  // indices into pids_, fast PIDs twice
  size_t next_{0};

  text_sensor::TextSensor *vin_sensor_{nullptr};
  text_sensor::TextSensor *dtc_sensor_{nullptr};
  sensor::Sensor *dtc_count_sensor_{nullptr};
  bool vin_known_{false};
  uint32_t last_vin_try_{0};
  bool want_dtc_{false};
  bool want_clear_{false};
  uint32_t last_dtc_{0};
  std::vector<std::string> dtcs_;
  bool dtc_replied_{false};
  Pending pending_{Pending::NONE};
  uint32_t pending_since_{0};

  int tx_pin_{-1};
  int rx_pin_{-1};
  uint32_t bit_rate_{500000};
  uint32_t poll_interval_{250};
  uint32_t dtc_interval_{300000};
  uint32_t last_poll_{0};
  GPIOPin *standby_pin_{nullptr};

  twai_node_handle_t node_{nullptr};
  QueueHandle_t rx_queue_{nullptr};
  bool active_{false};
  std::atomic<uint8_t> tx_inflight_{0};
  std::atomic<bool> bus_off_{false};
  uint8_t tx_head_{0};
  uint8_t tx_buf_[TX_SLOTS][8]{};
  twai_frame_t tx_frame_[TX_SLOTS]{};
  IsoTpRx rx_[NUM_ECUS];
};

class ClearDtcButton : public button::Button, public Parented<Obd2Component> {
 protected:
  void press_action() override { this->parent_->clear_dtcs(); }
};

}  // namespace esphome::obd2
