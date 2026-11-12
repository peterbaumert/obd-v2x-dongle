#pragma once

#include "esphome/components/adc/adc_sensor.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/deep_sleep/deep_sleep_component.h"
#include "esphome/components/number/number.h"
#include "esphome/components/switch/switch.h"
#include "esphome/core/automation.h"
#include "esphome/core/component.h"
#include "esphome/core/helpers.h"

namespace esphome::power_manager {

enum class Mode : uint8_t { CHECK, DRIVING, PARKED, REPORT, SHUTDOWN, SLEEPING };

class PowerManager : public Component {
 public:
  void set_deep_sleep(deep_sleep::DeepSleepComponent *ds) { this->deep_sleep_ = ds; }
  void set_battery_adc(adc::ADCSensor *adc) { this->adc_ = adc; }
  void set_voltage_multiplier(float m) { this->multiplier_ = m; }
  void set_modem_status(binary_sensor::BinarySensor *s) { this->modem_status_ = s; }
  void set_stay_awake(switch_::Switch *s) { this->stay_awake_ = s; }
  void set_engine_on_voltage(number::Number *n) { this->engine_on_v_ = n; }
  void set_unplugged_voltage(number::Number *n) { this->unplugged_v_ = n; }
  void set_low_battery_voltage(number::Number *n) { this->low_batt_v_ = n; }
  void set_parking_delay(number::Number *n) { this->parking_delay_ = n; }
  void set_check_interval(number::Number *n) { this->check_interval_ = n; }
  void set_report_interval(number::Number *n) { this->report_interval_ = n; }
  void set_low_battery_report_interval(number::Number *n) { this->low_batt_interval_ = n; }
  void set_report_timeout(number::Number *n) { this->report_timeout_ = n; }

  template<typename F> void add_on_network_callback(F &&cb) { this->on_network_.add(std::forward<F>(cb)); }
  template<typename F> void add_on_shutdown_callback(F &&cb) { this->on_shutdown_.add(std::forward<F>(cb)); }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

  /// A position report went out (MQTT/Traccar): in REPORT mode the dongle may go back to sleep.
  void report_done();
  Mode get_mode() const { return this->mode_; }
  const char *get_mode_str() const;
  /// Car battery as measured at the last wake / by the last sample
  float get_voltage() const { return this->voltage_; }

 protected:
  float sample_voltage_();
  float setting_(number::Number *n, float fallback) const;
  void enter_(Mode mode);
  void start_network_();
  bool stay_awake_on_() const { return this->stay_awake_ != nullptr && this->stay_awake_->state; }

  deep_sleep::DeepSleepComponent *deep_sleep_{nullptr};
  adc::ADCSensor *adc_{nullptr};
  float multiplier_{1.0f};
  binary_sensor::BinarySensor *modem_status_{nullptr};
  switch_::Switch *stay_awake_{nullptr};
  number::Number *engine_on_v_{nullptr};
  number::Number *unplugged_v_{nullptr};
  number::Number *low_batt_v_{nullptr};
  number::Number *parking_delay_{nullptr};
  number::Number *check_interval_{nullptr};
  number::Number *report_interval_{nullptr};
  number::Number *low_batt_interval_{nullptr};
  number::Number *report_timeout_{nullptr};

  CallbackManager<void()> on_network_;
  CallbackManager<void()> on_shutdown_;

  Mode mode_{Mode::CHECK};
  bool network_started_{false};
  bool reported_{false};
  float voltage_{NAN};
  uint32_t mode_since_{0};
  uint32_t last_sample_{0};
  uint32_t engine_off_since_{0};
};

class NetworkTrigger : public Trigger<> {
 public:
  explicit NetworkTrigger(PowerManager *parent) {
    parent->add_on_network_callback([this]() { this->trigger(); });
  }
};

class ShutdownTrigger : public Trigger<> {
 public:
  explicit ShutdownTrigger(PowerManager *parent) {
    parent->add_on_shutdown_callback([this]() { this->trigger(); });
  }
};

template<typename... Ts> class ReportDoneAction : public Action<Ts...>, public Parented<PowerManager> {
 public:
  void play(const Ts &...x) override { this->parent_->report_done(); }
};

}  // namespace esphome::power_manager
