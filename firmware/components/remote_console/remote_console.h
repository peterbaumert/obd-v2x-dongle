#pragma once

#include <functional>
#include <string>

#include "esphome/core/component.h"
#include "esphome/core/defines.h"
#include "esphome/core/hal.h"

#ifdef USE_REMOTE_CONSOLE_OBD2
#include "esphome/components/obd2/obd2.h"
#endif
#ifdef USE_REMOTE_CONSOLE_MODEM
#include "esphome/components/modem/modem_component.h"
#endif

namespace esphome::remote_console {

/// Line-based TCP console for diagnostics through the WireGuard tunnel (one session, plain text).
class RemoteConsole : public Component {
 public:
  void set_listen_address(const char *address) { this->listen_address_ = address; }
  void set_port(uint16_t port) { this->port_ = port; }
  void set_password(const char *password) { this->password_ = password; }
  void set_idle_timeout(uint32_t ms) { this->idle_timeout_ = ms; }
  void set_status(std::function<std::string()> &&f) { this->status_ = std::move(f); }
#ifdef USE_REMOTE_CONSOLE_OBD2
  void set_obd2(obd2::Obd2Component *obd) { this->obd_ = obd; }
#endif
#ifdef USE_REMOTE_CONSOLE_MODEM
  void set_modem(modem::ModemComponent *modem) { this->modem_ = modem; }
#endif

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_CONNECTION; }

  /// Open (true) or close (false) the port; closing ends a running session.
  void set_enabled(bool enabled);
  bool is_enabled() const { return this->enabled_; }
  /// A session is open (keeps the dongle awake, see power_manager's keep_awake)
  bool has_client() const { return this->client_ >= 0; }

 protected:
  static constexpr size_t LINE_SIZE = 160;

  void open_();
  void close_listener_();
  void accept_();
  void read_();
  void drop_client_(const char *reason);
  void handle_line_(char *line);
  void prompt_();
  void write_(const char *data, size_t len);
  void print_(const char *text);
  void printf_(const char *format, ...) __attribute__((format(printf, 2, 3)));
  void on_log_(uint8_t level, const char *tag, const char *message, size_t len);
  void cmd_status_();
  void cmd_log_(const char *arg);
  void cmd_obd_(const char *arg);
  void cmd_at_(const char *command);

  const char *listen_address_{nullptr};
  uint16_t port_{2323};
  const char *password_{nullptr};
  uint32_t idle_timeout_{600000};
  std::function<std::string()> status_;
#ifdef USE_REMOTE_CONSOLE_OBD2
  obd2::Obd2Component *obd_{nullptr};
  uint8_t obd_answers_{0};
#endif
#ifdef USE_REMOTE_CONSOLE_MODEM
  modem::ModemComponent *modem_{nullptr};
  std::string at_wait_;  // command whose reply (the modem component's log line) is awaited
  uint32_t at_deadline_{0};
#endif

  bool enabled_{false};
  int listener_{-1};
  int client_{-1};
  bool authed_{false};
  uint8_t auth_failures_{0};
  bool drop_pending_{false};  // send failed inside the log listener: close from loop()
  uint8_t log_level_{0};      // 0 = no live log, otherwise the highest level shown
  uint8_t iac_skip_{0};       // telnet option bytes still to skip
  bool overflow_{false};
  size_t line_len_{0};
  char line_[LINE_SIZE];
  uint32_t last_poll_{0};
  uint32_t last_open_try_{0};
  uint32_t last_activity_{0};
};

}  // namespace esphome::remote_console
