#include "obd2.h"

#include <cstring>

#include "esphome/core/log.h"

namespace esphome::obd2 {

static const char *const TAG = "obd2";
static const uint32_t OBD_REQUEST_ID = 0x7DF;   // functional request address
static const uint32_t OBD_RESPONSE_ID = 0x7E8;  // ECU responses 0x7E8..0x7EF
static const uint32_t ECU_REQUEST_OFFSET = 8;   // physical request address = response address - 8 (0x7E0..0x7E7)
static const uint32_t REPLY_WINDOW_MS = 1000;   // collect answers of all ECUs to a VIN / DTC / clear request
static const uint32_t VIN_RETRY_MS = 30000;
static const uint8_t PAD = 0x55;
static const uint32_t RESTORE_PREF_VERSION = 0x0B2D5160;  // keeps the signal store apart from other entity prefs

void Obd2Component::add_number(uint8_t signal, uint16_t can_id, uint8_t start, uint8_t len, bool little, float scale,
                               float offset) {
  this->profiles_.back().defs.push_back({can_id, signal, SignalKind::NUMBER, start, len, little, 0, scale, offset, {}, {}});
}

void Obd2Component::add_flag(uint8_t signal, uint16_t can_id, uint8_t start, uint8_t mask) {
  this->profiles_.back().defs.push_back({can_id, signal, SignalKind::FLAG, start, 1, false, mask, 1, 0, {}, {}});
}

void Obd2Component::add_enum(uint8_t signal, uint16_t can_id, uint8_t start, uint8_t len, bool little,
                             uint32_t mask) {
  this->profiles_.back().defs.push_back({can_id, signal, SignalKind::ENUM, start, len, little, mask, 1, 0, {}, {}});
}

void Obd2Component::add_enum_value(uint32_t raw, const char *name, bool on) {
  this->profiles_.back().defs.back().values.push_back({raw, name, on});
}

void Obd2Component::add_invalid(uint32_t raw) { this->profiles_.back().defs.back().invalid.push_back(raw); }

void Obd2Component::set_profile(int index) {
  if (index < 0 || index >= static_cast<int>(this->profiles_.size()))
    index = -1;
  this->profile_ = index;
  // The ISR queues only these IDs: the OBD responses plus the profile's broadcast frames
  for (auto &w : this->want_ids_)
    w = 0;
  for (uint32_t id = OBD_RESPONSE_ID; id < OBD_RESPONSE_ID + NUM_ECUS; id++)
    this->want_id_(id);
  const Profile *p = index < 0 ? nullptr : &this->profiles_[index];
  if (p != nullptr)
    for (const auto &d : p->defs)
      this->want_id_(d.can_id);

  for (size_t i = 0; i < this->outs_.size(); i++) {
    SignalOut &o = this->outs_[i];
    o.known = false;
    o.dirty = false;
    const SignalDef *def = nullptr;
    if (p != nullptr)
      for (const auto &d : p->defs)
        if (d.signal == i) {
          def = &d;
          break;
        }
    if (def != nullptr && o.restore && o.saved.valid && o.saved.profile == index) {
      this->apply_(*def, o, o.saved.raw);  // last known value from flash until the bus says otherwise
    } else if (def == nullptr && o.sensor != nullptr) {
      o.sensor->publish_state(NAN);  // the profile doesn't have this signal
    }
  }
  if (p == nullptr)
    ESP_LOGI(TAG, "Vehicle profile: none (OBD requests only)");
  else
    ESP_LOGI(TAG, "Vehicle profile: %s (%u signals)", p->title, static_cast<unsigned>(p->defs.size()));
}

void Obd2Component::save_signals_() {
  bool any = false;
  for (auto &o : this->outs_) {
    if (!o.restore || !o.save_dirty)
      continue;
    o.pref.save(&o.saved);
    o.save_dirty = false;
    any = true;
  }
  if (any)
    global_preferences->sync();  // a few writes per drive: at engine stop and when listening ends
}

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

  this->rx_queue_ = xQueueCreate(64, sizeof(RxFrame));
  for (auto &o : this->outs_) {
    if (!o.restore)
      continue;
    EntityBase *e = o.sensor != nullptr ? static_cast<EntityBase *>(o.sensor)
                    : o.binary != nullptr ? static_cast<EntityBase *>(o.binary)
                                          : static_cast<EntityBase *>(o.text);
    if (e == nullptr) {
      o.restore = false;
      continue;
    }
    o.pref = e->make_entity_preference<SavedRaw>(RESTORE_PREF_VERSION);
    if (!o.pref.load(&o.saved))
      o.saved = {-1, 0, 0};
  }
  this->set_profile(this->profile_);  // OBD response IDs; the profile select sets the real one later

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
  // Accept every standard frame; the ISR keeps only the IDs in want_ids_ (the profile can change at runtime,
  // the hardware filter only while the node is stopped)
  twai_mask_filter_config_t filter{};
  filter.id = 0;
  filter.mask = 0;
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

void Obd2Component::enable_node_() {
  if (this->node_enabled_)
    return;
  if (this->standby_pin_ != nullptr)
    this->standby_pin_->digital_write(false);
  twai_node_enable(this->node_);
  this->node_enabled_ = true;
}

void Obd2Component::disable_node_() {
  this->listening_ = false;
  this->save_signals_();
  if (!this->node_enabled_)
    return;
  twai_node_disable(this->node_);
  if (this->standby_pin_ != nullptr)
    this->standby_pin_->digital_write(true);
  this->node_enabled_ = false;
  ESP_LOGI(TAG, "Stopped: CAN controller off, transceiver in standby");
}

void Obd2Component::set_active(bool active) {
  if (active == this->active_ || this->node_ == nullptr)
    return;
  this->active_ = active;
  if (active) {
    this->listening_ = false;
    this->tx_inflight_ = 0;
    this->tx_head_ = 0;
    this->bus_off_ = false;
    for (auto &r : this->rx_)
      r.busy = false;
    this->pending_ = Pending::NONE;
    this->want_dtc_ = this->dtc_sensor_ != nullptr || this->dtc_count_sensor_ != nullptr;
    this->last_vin_try_ = millis() - VIN_RETRY_MS;
    this->enable_node_();
    ESP_LOGI(TAG, "Active: polling %u PIDs", static_cast<unsigned>(this->pids_.size()));
  } else {
    this->want_clear_ = false;
    this->save_signals_();  // values at engine stop (odometer, fuel, tyres); again when listening ends
    if (this->profile_ >= 0 && this->listen_after_stop_ > 0) {
      // Keep receiving the profile's broadcast frames (doors, lock) for a while; nothing is sent
      this->listening_ = true;
      this->listen_until_ = millis() + this->listen_after_stop_;
      ESP_LOGI(TAG, "Engine stopped: listening only for %u s", static_cast<unsigned>(this->listen_after_stop_ / 1000));
    } else {
      this->disable_node_();
    }
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
  const uint32_t id = frame.header.id;
  if (frame.header.ide || id >= 0x800 || !((self->want_ids_[id >> 5] >> (id & 31)) & 1))
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
  // Only while active (engine running): never transmit while just listening
  if (!this->active_)
    return false;
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
  this->publish_signals_(millis());

  if (!this->active_) {
    if (this->listening_ && static_cast<int32_t>(millis() - this->listen_until_) >= 0)
      this->disable_node_();
    return;
  }
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

void Obd2Component::decode_signals_(const RxFrame &f) {
  if (this->profile_ < 0)
    return;
  for (const auto &d : this->profiles_[this->profile_].defs)
    if (d.can_id == f.id)
      this->decode_(d, f);
}

void Obd2Component::decode_(const SignalDef &d, const RxFrame &f) {
  if (d.start + d.len > f.len)
    return;
  uint32_t raw = 0;
  if (d.kind == SignalKind::FLAG) {
    raw = (f.data[d.start] & d.mask) != 0;
  } else {
    for (uint8_t i = 0; i < d.len; i++) {
      const uint32_t b = f.data[d.start + i];
      raw = d.little ? raw | (b << (8 * i)) : (raw << 8) | b;
    }
    if (d.kind == SignalKind::ENUM && d.mask != 0)
      raw &= d.mask;  // other bits of the byte belong to other signals
  }
  if (d.kind == SignalKind::NUMBER)
    for (uint32_t v : d.invalid)
      if (v == raw)
        return;  // "not available" (tyre sensors not reported yet, engine just stopped): keep the last value
  SignalOut &o = this->outs_[d.signal];
  if (o.known && o.raw == raw)
    return;
  this->apply_(d, o, raw);
}

void Obd2Component::apply_(const SignalDef &d, SignalOut &o, uint32_t raw) {
  o.known = true;
  o.raw = raw;
  if (o.restore && (!o.saved.valid || o.saved.raw != raw || o.saved.profile != this->profile_)) {
    o.saved = {static_cast<int8_t>(this->profile_), 1, raw};
    o.save_dirty = true;  // written to flash at engine stop / end of listening, not on every change
  }
  switch (d.kind) {
    case SignalKind::NUMBER:
      o.value = raw * d.scale + d.offset;
      o.dirty = true;  // numbers are rate limited in publish_signals_()
      break;
    case SignalKind::FLAG:
      if (o.binary != nullptr)
        o.binary->publish_state(raw != 0);
      break;
    case SignalKind::ENUM: {
      const EnumValue *found = nullptr;
      bool has_on = false;
      for (const auto &v : d.values) {
        has_on |= v.on;
        if (v.raw == raw)
          found = &v;
      }
      if (o.binary != nullptr && has_on)
        o.binary->publish_state(found != nullptr && found->on);
      if (o.text != nullptr) {
        if (found != nullptr) {
          o.text->publish_state(found->name);
        } else {
          char buf[24];
          snprintf(buf, sizeof(buf), "unknown 0x%0*X", d.len * 2, static_cast<unsigned>(raw));
          o.text->publish_state(buf);
        }
      }
      break;
    }
  }
}

void Obd2Component::publish_signals_(uint32_t now) {
  for (auto &o : this->outs_) {
    if (!o.dirty || now - o.last_pub < this->signal_interval_)
      continue;
    o.dirty = false;
    o.last_pub = now;
    if (o.sensor != nullptr)
      o.sensor->publish_state(o.value);
  }
}

void Obd2Component::handle_frame_(const RxFrame &f) {
  this->decode_signals_(f);
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
  ESP_LOGCONFIG(TAG, "  Vehicle profiles: %u compiled, active: %s, listen after stop: %u s",
                static_cast<unsigned>(this->profiles_.size()),
                this->profile_ < 0 ? "none" : this->profiles_[this->profile_].title,
                static_cast<unsigned>(this->listen_after_stop_ / 1000));
  LOG_PIN("  Standby pin: ", this->standby_pin_);
}

}  // namespace esphome::obd2
