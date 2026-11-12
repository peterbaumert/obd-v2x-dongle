#include "ec200u_gnss.h"

#include <cstdlib>
#include <cstring>
#include <ctime>

#include "esphome/components/logger/logger.h"
#include "esphome/core/log.h"

namespace esphome::ec200u_gnss {

static const char *const TAG = "ec200u_gnss";
static const uint8_t CBC_EVERY = 6;  // supply voltage every 6th update (30 s at 5 s)

void Ec200uGnss::setup() {
  if (logger::global_logger == nullptr) {
    this->mark_failed();
    return;
  }
  // The modem component logs every send_at() reply ("AT '<cmd>' -> OK: <reply>"); log listeners run in the
  // main loop (messages from the modem task are queued), so parsing here is single-threaded.
  logger::global_logger->add_log_callback(
      this, [](void *self, uint8_t level, const char *tag, const char *message, size_t len) {
        if (strcmp(tag, "modem") == 0)
          static_cast<Ec200uGnss *>(self)->on_log_(message, len);
      });
  this->modem_->add_on_state_callback([this](modem::ModemState state) {
    if (state == modem::ModemState::MODEM_STATE_CONNECTED)
      this->start_pending_ = true;
  });
}

void Ec200uGnss::update() {
  if (!this->modem_->is_connected())
    return;
  if (this->start_pending_ || !this->started_) {
    // GNSS on (also fine if already running: the modem answers +CME ERROR: 504)
    if (this->modem_->send_at("AT+QGPS=1")) {
      this->start_pending_ = false;
      this->started_ = true;
    }
    return;
  }
  if (this->supply_voltage_sensor_ != nullptr && this->cbc_countdown_-- == 0) {
    this->cbc_countdown_ = CBC_EVERY - 1;
    this->modem_->send_at("AT+CBC");
    return;
  }
  this->modem_->send_at("AT+QGPSLOC=2", 2000);
}

void Ec200uGnss::on_log_(const char *message, size_t len) {
  const std::string line(message, len);
  const size_t cbc = line.find("+CBC:");
  if (cbc != std::string::npos) {
    this->parse_cbc_(line.c_str() + cbc + 5);
    return;
  }
  const size_t at = line.find("+QGPSLOC:");
  if (at != std::string::npos) {
    if (this->parse_qgpsloc_(line.c_str() + at + 9)) {
      this->fix_valid_ = true;
      this->fix_ms_ = millis();
      const Fix &f = this->fix_;
      if (this->latitude_sensor_ != nullptr)
        this->latitude_sensor_->publish_state(f.latitude);
      if (this->longitude_sensor_ != nullptr)
        this->longitude_sensor_->publish_state(f.longitude);
      if (this->altitude_sensor_ != nullptr)
        this->altitude_sensor_->publish_state(f.altitude);
      if (this->speed_sensor_ != nullptr)
        this->speed_sensor_->publish_state(f.speed);
      if (this->course_sensor_ != nullptr)
        this->course_sensor_->publish_state(f.course);
      if (this->hdop_sensor_ != nullptr)
        this->hdop_sensor_->publish_state(f.hdop);
      if (this->satellites_sensor_ != nullptr)
        this->satellites_sensor_->publish_state(f.satellites);
      this->on_fix_.call(f);
    }
    return;
  }
  if (line.find("QGPSLOC") != std::string::npos && line.find("CME ERROR: 505") != std::string::npos) {
    // GNSS session not active (modem restarted): switch it on again
    this->start_pending_ = true;
  } else if (line.find("QGPSLOC") != std::string::npos && line.find("CME ERROR: 516") != std::string::npos) {
    // No fix yet
    if (this->satellites_sensor_ != nullptr && this->fix_valid_ && !this->has_fix())
      this->satellites_sensor_->publish_state(0);
  }
}

// +QGPSLOC: <UTC hhmmss.sss>,<lat>,<lon>,<hdop>,<altitude>,<fix>,<cog>,<spkm>,<spkn>,<date ddmmyy>,<nsat>
// (mode 2: latitude/longitude in signed decimal degrees)
bool Ec200uGnss::parse_qgpsloc_(const char *p) {
  const char *fields[11];
  int n = 0;
  while (*p == ' ')
    p++;
  fields[n++] = p;
  for (const char *c = p; *c != '\0' && *c != '\r' && *c != '\n' && n < 11; c++)
    if (*c == ',')
      fields[n++] = c + 1;
  if (n < 11)
    return false;
  Fix f{};
  f.utc_time = static_cast<uint32_t>(strtof(fields[0], nullptr));
  f.latitude = strtof(fields[1], nullptr);
  f.longitude = strtof(fields[2], nullptr);
  f.hdop = strtof(fields[3], nullptr);
  f.altitude = strtof(fields[4], nullptr);
  const int fix_type = atoi(fields[5]);
  // COG is ddd.mm (degrees, minutes)
  const float cog = strtof(fields[6], nullptr);
  f.course = static_cast<int>(cog) + (cog - static_cast<int>(cog)) * 100.0f / 60.0f;
  f.speed = strtof(fields[7], nullptr);
  f.utc_date = static_cast<uint32_t>(strtoul(fields[9], nullptr, 10));
  f.satellites = atoi(fields[10]);
  if (fix_type < 2 || (f.latitude == 0.0f && f.longitude == 0.0f))
    return false;
  this->fix_ = f;
  return true;
}

// +CBC: <bcs>,<bcl>,<voltage mV>
void Ec200uGnss::parse_cbc_(const char *p) {
  const char *c = strrchr(p, ',');
  if (c == nullptr)
    return;
  const long mv = strtol(c + 1, nullptr, 10);
  if (mv > 2000 && mv < 5000)
    this->supply_voltage_sensor_->publish_state(mv / 1000.0f);
}

uint32_t Ec200uGnss::get_fix_epoch() const {
  if (!this->fix_valid_ || this->fix_.utc_date == 0)
    return 0;
  struct tm t {};
  t.tm_mday = this->fix_.utc_date / 10000;
  t.tm_mon = (this->fix_.utc_date / 100) % 100 - 1;
  t.tm_year = this->fix_.utc_date % 100 + 100;
  t.tm_hour = this->fix_.utc_time / 10000;
  t.tm_min = (this->fix_.utc_time / 100) % 100;
  t.tm_sec = this->fix_.utc_time % 100;
  // days since epoch without timegm (not in newlib): civil-from-days algorithm
  int y = t.tm_year + 1900, m = t.tm_mon + 1, d = t.tm_mday;
  y -= m <= 2;
  const int era = (y >= 0 ? y : y - 399) / 400;
  const unsigned yoe = static_cast<unsigned>(y - era * 400);
  const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  const long days = static_cast<long>(era) * 146097 + static_cast<long>(doe) - 719468;
  return static_cast<uint32_t>(days * 86400L + t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec);
}

void Ec200uGnss::dump_config() {
  ESP_LOGCONFIG(TAG, "EC200U GNSS (AT+QGPSLOC over the modem's AT channel)");
  LOG_UPDATE_INTERVAL(this);
}

}  // namespace esphome::ec200u_gnss
