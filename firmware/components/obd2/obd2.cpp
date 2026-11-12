#include "obd2.h"

#include "esphome/core/log.h"

namespace esphome::obd2 {

static const char *const TAG = "obd2";
static const uint32_t OBD_REQUEST_ID = 0x7DF;   // functional request address
static const uint32_t OBD_RESPONSE_ID = 0x7E8;  // ECU responses 0x7E8..0x7EF
static const uint32_t OBD_RESPONSE_MASK = 0x7F8;

void Obd2Component::add_pid(uint8_t pid, sensor::Sensor *sens, bool fast) {
  this->pids_.push_back({pid, sens});
  const uint8_t idx = this->pids_.size() - 1;
  this->schedule_.push_back(idx);
  if (fast)
    this->schedule_.push_back(idx);
}

void Obd2Component::setup() {
  if (this->standby_pin_ != nullptr) {
    this->standby_pin_->setup();
    this->standby_pin_->digital_write(true);  // standby until set_active(true)
  }
  // Interleave the second copies of the fast PIDs: [fast..., slow..., fast...]
  std::vector<uint8_t> order;
  for (size_t i = 0; i < this->schedule_.size(); i++)
    if (i == 0 || this->schedule_[i] != this->schedule_[i - 1])
      order.push_back(this->schedule_[i]);
  for (size_t i = 1; i < this->schedule_.size(); i++)
    if (this->schedule_[i] == this->schedule_[i - 1])
      order.push_back(this->schedule_[i]);
  this->schedule_ = order;

  this->rx_queue_ = xQueueCreate(16, sizeof(RxFrame));

  twai_onchip_node_config_t cfg{};
  cfg.io_cfg.tx = static_cast<gpio_num_t>(this->tx_pin_);
  cfg.io_cfg.rx = static_cast<gpio_num_t>(this->rx_pin_);
  cfg.io_cfg.quanta_clk_out = GPIO_NUM_NC;
  cfg.io_cfg.bus_off_indicator = GPIO_NUM_NC;
  cfg.bit_timing.bitrate = this->bit_rate_;
  cfg.tx_queue_depth = 1;
  cfg.fail_retry_cnt = 3;
  cfg.flags.no_receive_rtr = 1;
  if (this->rx_queue_ == nullptr || twai_new_node_onchip(&cfg, &this->node_) != ESP_OK) {
    ESP_LOGE(TAG, "TWAI node setup failed");
    this->mark_failed();
    return;
  }
  twai_mask_filter_config_t filter{};
  filter.id = OBD_RESPONSE_ID;
  filter.mask = OBD_RESPONSE_MASK;
  twai_node_config_mask_filter(this->node_, 0, &filter);

  twai_event_callbacks_t cbs{};
  cbs.on_rx_done = &Obd2Component::on_rx_;
  cbs.on_tx_done = &Obd2Component::on_tx_done_;
  cbs.on_state_change = &Obd2Component::on_state_;
  twai_node_register_event_callbacks(this->node_, &cbs, this);

  this->tx_frame_.header.id = OBD_REQUEST_ID;
  this->tx_frame_.header.dlc = 8;
  this->tx_frame_.buffer = this->tx_buf_;
  this->tx_frame_.buffer_len = sizeof(this->tx_buf_);
}

void Obd2Component::set_active(bool active) {
  if (active == this->active_ || this->node_ == nullptr)
    return;
  this->active_ = active;
  if (active) {
    if (this->standby_pin_ != nullptr)
      this->standby_pin_->digital_write(false);
    this->tx_busy_ = false;
    this->bus_off_ = false;
    twai_node_enable(this->node_);
    ESP_LOGI(TAG, "Active: polling %u PIDs", static_cast<unsigned>(this->pids_.size()));
  } else {
    twai_node_disable(this->node_);
    if (this->standby_pin_ != nullptr)
      this->standby_pin_->digital_write(true);
    ESP_LOGI(TAG, "Stopped: CAN controller off, transceiver in standby");
  }
}

bool IRAM_ATTR Obd2Component::on_rx_(twai_node_handle_t node, const twai_rx_done_event_data_t *edata, void *ctx) {
  auto *self = static_cast<Obd2Component *>(ctx);
  uint8_t buf[8];
  twai_frame_t frame{};
  frame.buffer = buf;
  frame.buffer_len = sizeof(buf);
  if (twai_node_receive_from_isr(node, &frame) != ESP_OK)
    return false;
  RxFrame rx{};
  rx.id = frame.header.id;
  rx.len = frame.header.dlc > 8 ? 8 : frame.header.dlc;
  for (uint8_t i = 0; i < rx.len; i++)
    rx.data[i] = buf[i];
  BaseType_t woken = pdFALSE;
  xQueueSendFromISR(self->rx_queue_, &rx, &woken);
  return woken == pdTRUE;
}

bool IRAM_ATTR Obd2Component::on_tx_done_(twai_node_handle_t, const twai_tx_done_event_data_t *, void *ctx) {
  static_cast<Obd2Component *>(ctx)->tx_busy_ = false;
  return false;
}

bool IRAM_ATTR Obd2Component::on_state_(twai_node_handle_t, const twai_state_change_event_data_t *edata, void *ctx) {
  if (edata->new_sta == TWAI_ERROR_BUS_OFF)
    static_cast<Obd2Component *>(ctx)->bus_off_ = true;
  return false;
}

void Obd2Component::loop() {
  RxFrame rx;
  while (this->rx_queue_ != nullptr && xQueueReceive(this->rx_queue_, &rx, 0) == pdTRUE)
    this->handle_(rx);

  if (!this->active_)
    return;
  if (this->bus_off_.exchange(false)) {
    ESP_LOGW(TAG, "Bus off, recovering");
    twai_node_recover(this->node_);
    this->tx_busy_ = false;
    return;
  }
  const uint32_t now = millis();
  if (now - this->last_poll_ >= this->poll_interval_) {
    this->last_poll_ = now;
    this->send_next_();
  }
}

void Obd2Component::send_next_() {
  if (this->schedule_.empty() || this->tx_busy_)
    return;
  const Pid &p = this->pids_[this->schedule_[this->next_++ % this->schedule_.size()]];
  // Single-frame mode 01 request, padded to 8 bytes
  const uint8_t req[8] = {0x02, 0x01, p.pid, 0x55, 0x55, 0x55, 0x55, 0x55};
  for (int i = 0; i < 8; i++)
    this->tx_buf_[i] = req[i];
  this->tx_busy_ = true;
  if (twai_node_transmit(this->node_, &this->tx_frame_, 0) != ESP_OK)
    this->tx_busy_ = false;
}

void Obd2Component::handle_(const RxFrame &f) {
  // Single frame: [PCI len, 0x41, pid, A, B, ...]
  if (f.len < 4 || (f.data[0] & 0xF0) != 0x00 || f.data[1] != 0x41)
    return;
  const uint8_t pid = f.data[2];
  const float a = f.data[3];
  const float b = f.len > 4 ? f.data[4] : 0;
  for (const auto &p : this->pids_) {
    if (p.pid != pid)
      continue;
    float v;
    switch (pid) {
      case 0x04:
      case 0x2F:
        v = a * 100.0f / 255.0f;
        break;
      case 0x05:
      case 0x0F:
      case 0x46:
        v = a - 40.0f;
        break;
      case 0x0C:
        v = (a * 256.0f + b) / 4.0f;
        break;
      case 0x0D:
        v = a;
        break;
      case 0x42:
        v = (a * 256.0f + b) / 1000.0f;
        break;
      default:
        return;
    }
    p.sensor->publish_state(v);
    return;
  }
}

void Obd2Component::dump_config() {
  ESP_LOGCONFIG(TAG,
                "OBD-II (CAN, ISO 15765-4 11-bit):\n"
                "  TX: GPIO%d, RX: GPIO%d\n"
                "  Bit rate: %u\n"
                "  Poll interval: %u ms, %u PIDs",
                this->tx_pin_, this->rx_pin_, static_cast<unsigned>(this->bit_rate_),
                static_cast<unsigned>(this->poll_interval_), static_cast<unsigned>(this->pids_.size()));
  LOG_PIN("  Standby pin: ", this->standby_pin_);
}

}  // namespace esphome::obd2
