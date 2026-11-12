#pragma once

#include <atomic>
#include <vector>

#include <esp_twai.h>
#include <esp_twai_onchip.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

#include "esphome/components/sensor/sensor.h"
#include "esphome/core/component.h"
#include "esphome/core/hal.h"

namespace esphome::obd2 {

struct RxFrame {
  uint32_t id;
  uint8_t len;
  uint8_t data[8];
};

/// OBD-II mode 01 polling over CAN (ISO 15765-4, 11-bit, single frames) on the TWAI node driver.
class Obd2Component : public Component {
 public:
  void set_pins(int tx, int rx) {
    this->tx_pin_ = tx;
    this->rx_pin_ = rx;
  }
  void set_bit_rate(uint32_t bit_rate) { this->bit_rate_ = bit_rate; }
  void set_poll_interval(uint32_t ms) { this->poll_interval_ = ms; }
  void set_standby_pin(GPIOPin *pin) { this->standby_pin_ = pin; }
  void add_pid(uint8_t pid, sensor::Sensor *sens, bool fast);

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::HARDWARE; }

  /// Start (true) or stop (false) talking on the bus; stopped = controller off, transceiver in standby.
  void set_active(bool active);
  bool is_active() const { return this->active_; }

 protected:
  static bool on_rx_(twai_node_handle_t node, const twai_rx_done_event_data_t *edata, void *ctx);
  static bool on_tx_done_(twai_node_handle_t node, const twai_tx_done_event_data_t *edata, void *ctx);
  static bool on_state_(twai_node_handle_t node, const twai_state_change_event_data_t *edata, void *ctx);
  void handle_(const RxFrame &frame);
  void send_next_();

  struct Pid {
    uint8_t pid;
    sensor::Sensor *sensor;
  };
  std::vector<Pid> pids_;
  std::vector<uint8_t> schedule_;  // indices into pids_, fast PIDs twice
  size_t next_{0};

  int tx_pin_{-1};
  int rx_pin_{-1};
  uint32_t bit_rate_{500000};
  uint32_t poll_interval_{250};
  uint32_t last_poll_{0};
  GPIOPin *standby_pin_{nullptr};

  twai_node_handle_t node_{nullptr};
  QueueHandle_t rx_queue_{nullptr};
  bool active_{false};
  std::atomic<bool> tx_busy_{false};
  std::atomic<bool> bus_off_{false};
  uint8_t tx_buf_[8]{};
  twai_frame_t tx_frame_{};
};

}  // namespace esphome::obd2
