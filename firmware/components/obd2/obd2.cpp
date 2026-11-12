#include "obd2.h"

#include <cstring>

#include "esphome/core/log.h"

namespace esphome::obd2 {

static const char *const TAG = "obd2";
static const uint32_t OBD_REQUEST_ID = 0x7DF;   // functional request address
static const uint32_t OBD_RESPONSE_ID = 0x7E8;  // ECU responses 0x7E8..0x7EF
static const uint32_t OBD_RESPONSE_MASK = 0x7F8;
static const uint32_t ECU_REQUEST_OFFSET = 8;   // physical request address = response address - 8 (0x7E0..0x7E7)
static const uint32_t REPLY_WINDOW_MS = 1000;   // collect answers of all ECUs to a VIN / DTC / clear request
static const uint32_t VIN_RETRY_MS = 30000;
static const uint8_t PAD = 0x55;

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

  this->rx_queue_ = xQueueCreate(32, sizeof(RxFrame));

  twai_onchip_node_config_t cfg{};
  cfg.io_cfg.tx = static_cast<gpio_num_t>(this->tx_pin_);
  cfg.io_cfg.rx = static_cast<gpio_num_t>(this->rx_pin_);
  cfg.io_cfg.quanta_clk_out = GPIO_NUM_NC;
  cfg.io_cfg.bus_off_indicator = GPIO_NUM_NC;
  cfg.bit_timing.bitrate = this->bit_rate_;
  cfg.tx_queue_depth = TX_SLOTS;
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

  for (uint8_t i = 0; i < TX_SLOTS; i++) {
    this->tx_frame_[i].header.dlc = 8;
    this->tx_frame_[i].buffer = this->tx_buf_[i];
    this->tx_frame_[i].buffer_len = 8;
  }
}

void Obd2Component::set_active(bool active) {
  if (active == this->active_ || this->node_ == nullptr)
    return;
  this->active_ = active;
  if (active) {
    if (this->standby_pin_ != nullptr)
      this->standby_pin_->digital_write(false);
    this->tx_inflight_ = 0;
    this->tx_head_ = 0;
    this->bus_off_ = false;
    for (auto &r : this->rx_)
      r.busy = false;
    this->pending_ = Pending::NONE;
    this->want_dtc_ = this->dtc_sensor_ != nullptr || this->dtc_count_sensor_ != nullptr;
    this->last_vin_try_ = millis() - VIN_RETRY_MS;
    twai_node_enable(this->node_);
    ESP_LOGI(TAG, "Active: polling %u PIDs", static_cast<unsigned>(this->pids_.size()));
  } else {
    twai_node_disable(this->node_);
    if (this->standby_pin_ != nullptr)
      this->standby_pin_->digital_write(true);
    this->want_clear_ = false;
    ESP_LOGI(TAG, "Stopped: CAN controller off, transceiver in standby");
  }
}

void Obd2Component::clear_dtcs() {
  if (!this->active_) {
    ESP_LOGW(TAG, "Fault codes can only be cleared while the bus is active (engine running)");
    return;
  }
  this->want_clear_ = true;
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
  auto *self = static_cast<Obd2Component *>(ctx);
  if (self->tx_inflight_ > 0)
    self->tx_inflight_--;
  return false;
}

bool IRAM_ATTR Obd2Component::on_state_(twai_node_handle_t, const twai_state_change_event_data_t *edata, void *ctx) {
  if (edata->new_sta == TWAI_ERROR_BUS_OFF)
    static_cast<Obd2Component *>(ctx)->bus_off_ = true;
  return false;
}

bool Obd2Component::send_(uint32_t id, const uint8_t *data, uint8_t len) {
  // Frames finish in order, so with fewer than TX_SLOTS in flight the slot at tx_head_ is free
  if (this->tx_inflight_ >= TX_SLOTS)
    return false;
  const uint8_t slot = this->tx_head_;
  for (uint8_t i = 0; i < 8; i++)
    this->tx_buf_[slot][i] = i < len ? data[i] : PAD;
  this->tx_frame_[slot].header.id = id;
  this->tx_inflight_++;
  if (twai_node_transmit(this->node_, &this->tx_frame_[slot], 0) != ESP_OK) {
    this->tx_inflight_--;
    return false;
  }
  this->tx_head_ = (slot + 1) % TX_SLOTS;
  return true;
}

bool Obd2Component::request_(const uint8_t *payload, uint8_t len) {
  // Functional single-frame request: [PCI len, payload...]
  uint8_t f[8];
  f[0] = len;
  memcpy(f + 1, payload, len);
  return this->send_(OBD_REQUEST_ID, f, len + 1);
}

void Obd2Component::loop() {
  RxFrame rx;
  while (this->rx_queue_ != nullptr && xQueueReceive(this->rx_queue_, &rx, 0) == pdTRUE)
    this->handle_frame_(rx);

  if (!this->active_)
    return;
  if (this->bus_off_.exchange(false)) {
    ESP_LOGW(TAG, "Bus off, recovering");
    twai_node_recover(this->node_);
    this->tx_inflight_ = 0;
    this->tx_head_ = 0;
    return;
  }
  const uint32_t now = millis();

  // One request at a time: VIN / DTC / clear pause the live-data polling while the ECUs answer
  if (this->pending_ != Pending::NONE) {
    if (now - this->pending_since_ >= REPLY_WINDOW_MS)
      this->finish_pending_();
    return;
  }
  if (now - this->last_poll_ < this->poll_interval_)
    return;
  this->last_poll_ = now;

  Pending next = Pending::NONE;
  if (this->want_clear_) {
    static const uint8_t req[] = {0x04};
    if (this->request_(req, sizeof(req))) {
      ESP_LOGI(TAG, "Clearing fault codes (mode 04)");
      this->want_clear_ = false;
      next = Pending::CLEAR;
    }
  } else if (this->vin_sensor_ != nullptr && !this->vin_known_ && now - this->last_vin_try_ >= VIN_RETRY_MS) {
    static const uint8_t req[] = {0x09, 0x02};
    this->last_vin_try_ = now;
    if (this->request_(req, sizeof(req)))
      next = Pending::VIN;
  } else if ((this->dtc_sensor_ != nullptr || this->dtc_count_sensor_ != nullptr) &&
             (this->want_dtc_ || now - this->last_dtc_ >= this->dtc_interval_)) {
    static const uint8_t req[] = {0x03};
    if (this->request_(req, sizeof(req))) {
      this->want_dtc_ = false;
      this->last_dtc_ = now;
      this->dtcs_.clear();
      this->dtc_replied_ = false;
      next = Pending::DTC;
    }
  } else {
    this->poll_pid_();
  }
  if (next != Pending::NONE) {
    this->pending_ = next;
    this->pending_since_ = now;
  }
}

void Obd2Component::poll_pid_() {
  if (this->schedule_.empty())
    return;
  const Pid &p = this->pids_[this->schedule_[this->next_ % this->schedule_.size()]];
  const uint8_t req[] = {0x01, p.pid};
  if (this->request_(req, sizeof(req)))
    this->next_++;
}

void Obd2Component::finish_pending_() {
  const Pending done = this->pending_;
  this->pending_ = Pending::NONE;
  switch (done) {
    case Pending::DTC: {
      if (!this->dtc_replied_) {
        ESP_LOGW(TAG, "No ECU answered the fault code request");
        break;
      }
      std::string list;
      for (const auto &c : this->dtcs_) {
        if (!list.empty())
          list += ", ";
        list += c;
      }
      ESP_LOGI(TAG, "Fault codes: %s", list.empty() ? "none" : list.c_str());
      if (this->dtc_sensor_ != nullptr)
        this->dtc_sensor_->publish_state(list.empty() ? "none" : list);
      if (this->dtc_count_sensor_ != nullptr)
        this->dtc_count_sensor_->publish_state(this->dtcs_.size());
      break;
    }
    case Pending::CLEAR:
      this->want_dtc_ = true;  // read them back
      break;
    case Pending::VIN:
      if (!this->vin_known_)
        ESP_LOGD(TAG, "No VIN answer, retrying in %u s", static_cast<unsigned>(VIN_RETRY_MS / 1000));
      break;
    default:
      break;
  }
}

void Obd2Component::handle_frame_(const RxFrame &f) {
  if (f.id < OBD_RESPONSE_ID || f.id >= OBD_RESPONSE_ID + NUM_ECUS || f.len < 2)
    return;
  const uint8_t ecu = f.id - OBD_RESPONSE_ID;
  IsoTpRx &r = this->rx_[ecu];
  switch (f.data[0] >> 4) {
    case 0x0: {  // single frame
      const uint8_t len = f.data[0] & 0x0F;
      if (len == 0 || len > f.len - 1)
        return;
      this->handle_message_(ecu, f.data + 1, len);
      break;
    }
    case 0x1: {  // first frame: 12-bit length, 6 data bytes; answer with flow control "send all, no delay"
      const uint16_t len = ((f.data[0] & 0x0F) << 8) | f.data[1];
      if (f.len < 8 || len < 8 || len > MAX_MSG) {
        r.busy = false;
        return;
      }
      memcpy(r.buf, f.data + 2, 6);
      r.len = len;
      r.got = 6;
      r.next_sn = 1;
      r.busy = true;
      static const uint8_t fc[] = {0x30, 0x00, 0x00};
      this->send_(f.id - ECU_REQUEST_OFFSET, fc, sizeof(fc));
      break;
    }
    case 0x2: {  // consecutive frame
      if (!r.busy || (f.data[0] & 0x0F) != r.next_sn) {
        r.busy = false;
        return;
      }
      const uint16_t n = std::min<uint16_t>(f.len - 1, r.len - r.got);
      memcpy(r.buf + r.got, f.data + 1, n);
      r.got += n;
      r.next_sn = (r.next_sn + 1) & 0x0F;
      if (r.got >= r.len) {
        r.busy = false;
        this->handle_message_(ecu, r.buf, r.len);
      }
      break;
    }
    default:
      break;
  }
}

void Obd2Component::handle_message_(uint8_t ecu, const uint8_t *d, uint16_t n) {
  switch (d[0]) {
    case 0x41:  // mode 01 live data
      this->handle_pid_(d, n);
      break;
    case 0x43: {  // mode 03: [0x43, count, A1, B1, A2, B2, ...]
      this->dtc_replied_ = true;
      for (uint16_t i = 2; i + 1 < n; i += 2) {
        const uint8_t a = d[i], b = d[i + 1];
        if (a == 0 && b == 0)
          continue;
        static const char SYS[] = {'P', 'C', 'B', 'U'};
        char code[6];
        snprintf(code, sizeof(code), "%c%X%X%02X", SYS[a >> 6], (a >> 4) & 0x03, a & 0x0F, b);
        bool dup = false;
        for (const auto &c : this->dtcs_)
          dup |= c == code;
        if (!dup)
          this->dtcs_.emplace_back(code);
      }
      break;
    }
    case 0x44:
      ESP_LOGI(TAG, "ECU 0x%03X cleared its fault codes", static_cast<unsigned>(OBD_RESPONSE_ID + ecu));
      break;
    case 0x49:  // mode 09 PID 02: [0x49, 0x02, items, 17 x VIN]
      if (n >= 3 + 17 && d[1] == 0x02 && !this->vin_known_) {
        std::string vin(reinterpret_cast<const char *>(d + n - 17), 17);
        for (char c : vin)
          if (c < '0' || c > 'Z')
            return;
        this->vin_known_ = true;
        if (this->vin_sensor_ != nullptr)
          this->vin_sensor_->publish_state(vin);
      }
      break;
    case 0x7F:  // negative response [0x7F, service, NRC]; 0x78 = still working, answer follows
      if (n >= 3 && d[2] != 0x78)
        ESP_LOGW(TAG, "ECU 0x%03X rejected service 0x%02X: NRC 0x%02X%s",
                 static_cast<unsigned>(OBD_RESPONSE_ID + ecu), d[1], d[2],
                 d[2] == 0x22 ? " (conditions not correct, e.g. engine running)" : "");
      break;
    default:
      break;
  }
}

void Obd2Component::handle_pid_(const uint8_t *d, uint16_t n) {
  if (n < 3)
    return;
  const uint8_t pid = d[1];
  const float a = d[2];
  const float b = n > 3 ? d[3] : 0;
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
                "  Poll interval: %u ms, %u PIDs\n"
                "  Fault codes every %u s, VIN: %s",
                this->tx_pin_, this->rx_pin_, static_cast<unsigned>(this->bit_rate_),
                static_cast<unsigned>(this->poll_interval_), static_cast<unsigned>(this->pids_.size()),
                static_cast<unsigned>(this->dtc_interval_ / 1000), YESNO(this->vin_sensor_ != nullptr));
  LOG_PIN("  Standby pin: ", this->standby_pin_);
}

}  // namespace esphome::obd2
