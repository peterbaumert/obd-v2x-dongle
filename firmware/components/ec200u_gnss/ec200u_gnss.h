#pragma once

#include <string>

#include "esphome/components/modem/modem_component.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/core/component.h"
#include "esphome/core/helpers.h"

namespace esphome::ec200u_gnss {

struct Fix {
  float latitude;   // degrees, + = N
  float longitude;  // degrees, + = E
  float altitude;   // m
  float speed;      // km/h
  float course;     // degrees
  float hdop;
  int satellites;
  uint32_t utc_time;  // hhmmss
  uint32_t utc_date;  // ddmmyy
};

class Ec200uGnss : public PollingComponent {
 public:
  explicit Ec200uGnss(modem::ModemComponent *modem) : modem_(modem) {}

  void set_latitude_sensor(sensor::Sensor *s) { this->latitude_sensor_ = s; }
  void set_longitude_sensor(sensor::Sensor *s) { this->longitude_sensor_ = s; }
  void set_altitude_sensor(sensor::Sensor *s) { this->altitude_sensor_ = s; }
  void set_speed_sensor(sensor::Sensor *s) { this->speed_sensor_ = s; }
  void set_course_sensor(sensor::Sensor *s) { this->course_sensor_ = s; }
  void set_hdop_sensor(sensor::Sensor *s) { this->hdop_sensor_ = s; }
  void set_satellites_sensor(sensor::Sensor *s) { this->satellites_sensor_ = s; }
  void set_supply_voltage_sensor(sensor::Sensor *s) { this->supply_voltage_sensor_ = s; }

  void setup() override;
  void update() override;
  void dump_config() override;

  bool has_fix() const { return this->fix_valid_ && millis() - this->fix_ms_ < 3 * this->get_update_interval(); }
  const Fix &get_fix() const { return this->fix_; }
  /// Seconds since 1970 (UTC) of the last fix, 0 if unknown
  uint32_t get_fix_epoch() const;
  /// Called with every new fix (main loop)
  template<typename F> void add_on_fix_callback(F &&cb) { this->on_fix_.add(std::forward<F>(cb)); }

 protected:
  void on_log_(const char *message, size_t len);
  bool parse_qgpsloc_(const char *p);
  void parse_cbc_(const char *p);

  modem::ModemComponent *modem_;
  bool started_{false};
  bool start_pending_{false};
  bool fix_valid_{false};
  uint8_t cbc_countdown_{0};
  uint32_t fix_ms_{0};
  Fix fix_{};
  CallbackManager<void(const Fix &)> on_fix_;

  sensor::Sensor *latitude_sensor_{nullptr};
  sensor::Sensor *longitude_sensor_{nullptr};
  sensor::Sensor *altitude_sensor_{nullptr};
  sensor::Sensor *speed_sensor_{nullptr};
  sensor::Sensor *course_sensor_{nullptr};
  sensor::Sensor *hdop_sensor_{nullptr};
  sensor::Sensor *satellites_sensor_{nullptr};
  /// Modem supply (AT+CBC): the buck (~3.8 V) on car power, the backup cell when unplugged
  sensor::Sensor *supply_voltage_sensor_{nullptr};
};

}  // namespace esphome::ec200u_gnss
