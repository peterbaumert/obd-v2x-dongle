#include "power_manager.h"

#include <driver/usb_serial_jtag.h>
#include <esp_attr.h>
#include <esp_sleep.h>

#include "esphome/core/log.h"

namespace esphome::power_manager {

static const char *const TAG = "power_manager";
static const uint32_t RTC_MAGIC = 0x0B2D2026;
static const uint32_t SHUTDOWN_TIMEOUT_MS = 15000;  // modem: AT+QPOWD then STATUS low
static const uint32_t SAMPLE_INTERVAL_MS = 2000;
static const uint32_t USB_DETECT_MS = 500;  // time after boot to see the host's USB frames before sleeping

// Survive deep sleep (not a power loss): time since the last position report and the unplugged state
RTC_NOINIT_ATTR static uint32_t rtc_magic;
RTC_NOINIT_ATTR static uint32_t rtc_secs_since_report;
RTC_NOINIT_ATTR static uint32_t rtc_last_sleep_s;
RTC_NOINIT_ATTR static uint8_t rtc_unplugged;
RTC_NOINIT_ATTR static uint8_t rtc_cell_low;

void PowerManager::setup() {
  const bool from_sleep = esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_TIMER && rtc_magic == RTC_MAGIC;
  if (!from_sleep) {
    rtc_magic = RTC_MAGIC;
    rtc_secs_since_report = 0;
    rtc_last_sleep_s = 0;
    rtc_unplugged = 0;
    rtc_cell_low = 0;
  } else {
    rtc_secs_since_report += rtc_last_sleep_s;
  }

  this->voltage_ = this->sample_voltage_();
  const float v = this->voltage_;
  const bool engine = v > this->setting_(this->engine_on_v_, 13.2f);
  const bool unplugged = v < this->setting_(this->unplugged_v_, 6.0f);
  const bool low = !unplugged && v < this->setting_(this->low_batt_v_, 12.0f);
  const float interval_min =
      low ? this->setting_(this->low_batt_interval_, 120.0f) : this->setting_(this->report_interval_, 30.0f);

  if (!unplugged)
    rtc_cell_low = 0;  // car power is back: the cell charges again
  ESP_LOGI(TAG, "%s: car battery %.2f V, %u s since last report%s", from_sleep ? "Wake" : "Boot", v,
           static_cast<unsigned>(rtc_secs_since_report), rtc_cell_low ? ", backup cell low" : "");

  if (!from_sleep) {
    // Power-on (plugged in, flashed, reset): stay awake like after parking so it can be reached
    this->enter_(engine ? Mode::DRIVING : Mode::PARKED);
  } else if (engine) {
    this->enter_(Mode::DRIVING);
  } else if (rtc_cell_low) {
    this->enter_(this->usb_host_() ? Mode::PARKED : Mode::SLEEPING);  // no reports until plugged in again
  } else if (unplugged && !rtc_unplugged) {
    ESP_LOGI(TAG, "Unplugged since last wake: reporting");
    this->enter_(Mode::REPORT);
  } else if (rtc_secs_since_report >= interval_min * 60.0f) {
    this->enter_(Mode::REPORT);
  } else if (this->stay_awake_on_()) {
    this->enter_(Mode::PARKED);
  } else {
    this->enter_(Mode::SLEEPING);  // nothing to do: straight back to sleep
  }
  rtc_unplugged = unplugged ? 1 : 0;
}

float PowerManager::sample_voltage_() {
  if (this->adc_ == nullptr)
    return NAN;
  float sum = 0;
  int n = 0;
  for (int i = 0; i < 4; i++) {
    const float s = this->adc_->sample();
    if (!std::isnan(s)) {
      sum += s;
      n++;
    }
  }
  return n == 0 ? NAN : sum / n * this->multiplier_;
}

bool PowerManager::usb_host_() {
  // True only with a computer on USB-C (USB frames), not with a charger or power bank
  const bool usb = usb_serial_jtag_is_connected();
  if (usb && !this->usb_seen_)
    ESP_LOGI(TAG, "USB host connected: staying awake");
  this->usb_seen_ = usb;
  return usb;
}

bool PowerManager::stay_awake_on_() {
  // A low backup cell overrides the "Stay awake" switch (only a computer on USB-C keeps it awake then)
  return (this->stay_awake_ != nullptr && this->stay_awake_->state && !rtc_cell_low) || this->usb_host_();
}

bool PowerManager::unplugged_() const {
  return !std::isnan(this->voltage_) && this->voltage_ < this->setting_(this->unplugged_v_, 6.0f);
}

bool PowerManager::is_cell_low() const { return rtc_cell_low != 0; }

float PowerManager::setting_(number::Number *n, float fallback) const {
  return (n == nullptr || std::isnan(n->state)) ? fallback : n->state;
}

void PowerManager::start_network_() {
  if (this->network_started_)
    return;
  this->network_started_ = true;
  this->on_network_.call();
}

void PowerManager::enter_(Mode mode) {
  this->mode_ = mode;
  this->mode_since_ = millis();
  ESP_LOGI(TAG, "Mode: %s", this->get_mode_str());
  switch (mode) {
    case Mode::DRIVING:
    case Mode::REPORT:
      this->start_network_();
      break;
    case Mode::PARKED:
      this->engine_off_since_ = millis();
      this->start_network_();
      break;
    case Mode::SHUTDOWN:
      this->on_shutdown_.call();
      break;
    default:
      break;
  }
}

void PowerManager::report_done() {
  this->reported_ = true;
  rtc_secs_since_report = 0;
}

void PowerManager::loop() {
  const uint32_t now = millis();
  if (now - this->last_sample_ >= SAMPLE_INTERVAL_MS) {
    this->last_sample_ = now;
    const float v = this->sample_voltage_();
    if (!std::isnan(v))
      this->voltage_ = std::isnan(this->voltage_) ? v : this->voltage_ * 0.7f + v * 0.3f;  // light smoothing
  }
  const bool engine = this->voltage_ > this->setting_(this->engine_on_v_, 13.2f);

  // Unplugged: the dongle runs from the backup cell. Stop before the cell's protection cuts it off.
  if (!this->unplugged_()) {
    rtc_cell_low = 0;
  } else if (!rtc_cell_low && this->cell_voltage_ != nullptr && this->cell_voltage_->has_state() &&
             this->cell_voltage_->state < this->setting_(this->cell_cutoff_v_, 3.6f) &&
             (this->mode_ == Mode::DRIVING || this->mode_ == Mode::PARKED || this->mode_ == Mode::REPORT)) {
    ESP_LOGW(TAG, "Backup cell %.2f V: shutting down until car power returns", this->cell_voltage_->state);
    rtc_cell_low = 1;
    this->enter_(Mode::SHUTDOWN);
    return;
  }

  switch (this->mode_) {
    case Mode::DRIVING:
      if (!engine)
        this->enter_(Mode::PARKED);
      break;
    case Mode::PARKED:
      if (engine) {
        this->enter_(Mode::DRIVING);
      } else if (!this->stay_awake_on_() &&
                 now - this->engine_off_since_ >= this->setting_(this->parking_delay_, 5.0f) * 60000.0f) {
        this->enter_(Mode::SHUTDOWN);
      }
      break;
    case Mode::REPORT:
      if (engine) {
        this->enter_(Mode::DRIVING);
      } else if (this->stay_awake_on_()) {
        this->enter_(Mode::PARKED);
      } else if (this->reported_ ||
                 now - this->mode_since_ >= this->setting_(this->report_timeout_, 3.0f) * 60000.0f) {
        if (!this->reported_)
          ESP_LOGW(TAG, "Report timed out (no GPS fix / no network)");
        this->enter_(Mode::SHUTDOWN);
      }
      break;
    case Mode::SHUTDOWN: {
      const bool modem_off = this->modem_status_ == nullptr || !this->modem_status_->state;
      if (modem_off || now - this->mode_since_ >= SHUTDOWN_TIMEOUT_MS)
        this->enter_(Mode::SLEEPING);
      break;
    }
    case Mode::SLEEPING: {
      if (now < USB_DETECT_MS)
        break;  // give a connected computer a moment to show up
      if (this->stay_awake_on_()) {
        this->enter_(Mode::PARKED);
        break;
      }
      const uint32_t sleep_s = static_cast<uint32_t>(this->setting_(this->check_interval_, 60.0f));
      // Awake time counts towards the next report as well
      rtc_secs_since_report += now / 1000;
      rtc_last_sleep_s = sleep_s;
      ESP_LOGI(TAG, "Deep sleep for %u s", static_cast<unsigned>(sleep_s));
      this->deep_sleep_->set_sleep_duration(sleep_s * 1000);
      this->deep_sleep_->begin_sleep(true);
      break;
    }
    case Mode::CHECK:
      break;
  }
}

const char *PowerManager::get_mode_str() const {
  switch (this->mode_) {
    case Mode::CHECK:
      return "check";
    case Mode::DRIVING:
      return "driving";
    case Mode::PARKED:
      return "parked";
    case Mode::REPORT:
      return "report";
    case Mode::SHUTDOWN:
      return "shutdown";
    case Mode::SLEEPING:
      return "sleeping";
  }
  return "?";
}

void PowerManager::dump_config() {
  ESP_LOGCONFIG(TAG, "Power manager: mode %s, voltage multiplier %.2f, backup cell low: %s", this->get_mode_str(),
                this->multiplier_, YESNO(rtc_cell_low));
}

}  // namespace esphome::power_manager
