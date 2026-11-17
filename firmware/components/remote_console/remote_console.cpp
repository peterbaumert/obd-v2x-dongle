#include "remote_console.h"

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>

#include <esp_heap_caps.h>
#include <esp_system.h>
#include <lwip/sockets.h>

#include "esphome/components/logger/logger.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"
#include "esphome/core/version.h"

namespace esphome::remote_console {

static const char *const TAG = "remote_console";
static const uint32_t POLL_MS = 20;
static const uint32_t OPEN_RETRY_MS = 5000;
static const uint8_t MAX_AUTH_FAILURES = 3;
#ifdef USE_REMOTE_CONSOLE_MODEM
static const uint32_t AT_TIMEOUT_MS = 5000;
// Not from here: these cut the link the console runs on, change what the modem remembers, or cost money
static const char *const AT_BLOCKED[] = {"+IPR",  "+QPOWD", "+CFUN", "+CMUX", "+CGDCONT", "+QICSGP",    "+CPIN", "+CLCK",
                                         "+CPWD", "+CMGS",  "+CMSS", "+CUSD", "+QFOTADL", "+QPRTPARA", "&F",    "&W",
                                         "ATZ",   "ATD",    "ATA",   "ATO",   "ATH",      "ATE"};
#endif

static const char *const HELP =
    "status              uptime, memory, connection state\r\n"
    "log on|off          live log (or: log error|warn|info|debug)\r\n"
#ifdef USE_REMOTE_CONSOLE_OBD2
    "obd <hex bytes>     one read-only request to all ECUs, e.g. obd 01 0C, obd 22 F1 90\r\n"
    "obd 7E0 <hex bytes> the same to one ECU (7E0..7E7)\r\n"
#endif
#ifdef USE_REMOTE_CONSOLE_MODEM
    "AT...               modem command, e.g. AT+CSQ, AT+QENG=\"servingcell\"\r\n"
#endif
    "reboot              restart the dongle\r\n"
    "exit                close the session\r\n";

static void set_nonblocking(int fd) { lwip_fcntl(fd, F_SETFL, lwip_fcntl(fd, F_GETFL, 0) | O_NONBLOCK); }

static const char *skip_spaces(const char *p) {
  while (*p == ' ' || *p == '\t')
    p++;
  return p;
}

void RemoteConsole::setup() {
  if (logger::global_logger == nullptr)
    return;
  // Log listeners run in the main loop (messages from other tasks are queued first)
  logger::global_logger->add_log_callback(
      this, [](void *self, uint8_t level, const char *tag, const char *message, size_t len) {
        static_cast<RemoteConsole *>(self)->on_log_(level, tag, message, len);
      });
}

void RemoteConsole::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Remote console:\n"
                "  Address: %s:%u\n"
                "  Password: %s\n"
                "  Enabled: %s",
                this->listen_address_, this->port_, YESNO(this->password_ != nullptr), YESNO(this->enabled_));
}

void RemoteConsole::set_enabled(bool enabled) {
  if (enabled == this->enabled_)
    return;
  this->enabled_ = enabled;
  if (enabled) {
    this->last_open_try_ = millis() - OPEN_RETRY_MS;  // loop() opens the port once the network stack runs
  } else {
    this->drop_client_("console switched off");
    this->close_listener_();
  }
  ESP_LOGI(TAG, "Remote console %s", enabled ? "on" : "off");
}

void RemoteConsole::open_() {
  const int fd = lwip_socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0)
    return;  // network stack not up yet: tried again later
  int yes = 1;
  lwip_setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
  struct sockaddr_in addr {};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(this->port_);
  // The tunnel interface may not exist yet, so listen on every interface and check in accept_() where the
  // connection came in
  addr.sin_addr.s_addr = htonl(INADDR_ANY);
  if (lwip_bind(fd, reinterpret_cast<struct sockaddr *>(&addr), sizeof(addr)) != 0 || lwip_listen(fd, 1) != 0) {
    lwip_close(fd);
    return;
  }
  set_nonblocking(fd);
  this->listener_ = fd;
  ESP_LOGD(TAG, "Listening on port %u", this->port_);
}

void RemoteConsole::close_listener_() {
  if (this->listener_ >= 0)
    lwip_close(this->listener_);
  this->listener_ = -1;
}

void RemoteConsole::accept_() {
  struct sockaddr_in peer {};
  socklen_t len = sizeof(peer);
  const int fd = lwip_accept(this->listener_, reinterpret_cast<struct sockaddr *>(&peer), &len);
  if (fd < 0)
    return;
  struct sockaddr_in local {};
  len = sizeof(local);
  if (lwip_getsockname(fd, reinterpret_cast<struct sockaddr *>(&local), &len) != 0 ||
      local.sin_addr.s_addr != inet_addr(this->listen_address_)) {
    lwip_close(fd);  // not through the tunnel
    ESP_LOGW(TAG, "Connection on another interface refused");
    return;
  }
  // A new session replaces the old one (a session lost on the mobile link would block the port otherwise)
  this->drop_client_("replaced by a new session");
  set_nonblocking(fd);
  this->client_ = fd;
  this->authed_ = this->password_ == nullptr;
  this->auth_failures_ = 0;
  this->line_len_ = 0;
  this->overflow_ = false;
  this->iac_skip_ = 0;
  this->log_level_ = 0;
  this->drop_pending_ = false;
  this->last_activity_ = millis();
  char ip[16];
  inet_ntoa_r(peer.sin_addr, ip, sizeof(ip));
  ESP_LOGI(TAG, "Session from %s", ip);
  this->printf_("%s console (ESPHome %s). Type help.\r\n", App.get_name().c_str(), ESPHOME_VERSION);
  if (this->authed_) {
    this->prompt_();
  } else {
    this->print_("password: ");
  }
}

void RemoteConsole::drop_client_(const char *reason) {
  if (this->client_ < 0)
    return;
  const int fd = this->client_;
  this->client_ = -1;  // first, so nothing below writes to it any more
  this->drop_pending_ = false;
  lwip_close(fd);
#ifdef USE_REMOTE_CONSOLE_MODEM
  this->at_wait_.clear();
#endif
  ESP_LOGI(TAG, "Session closed: %s", reason);
}

void RemoteConsole::write_(const char *data, size_t len) {
  if (this->client_ < 0 || this->drop_pending_)
    return;
  while (len > 0) {
    const int n = lwip_send(this->client_, data, len, MSG_DONTWAIT);
    if (n > 0) {
      data += n;
      len -= n;
    } else if (errno == EAGAIN || errno == EWOULDBLOCK) {
      return;  // send buffer full (slow link): the rest of this output is dropped
    } else {
      this->drop_pending_ = true;  // closed in loop(): this may run inside the log listener
      return;
    }
  }
}

void RemoteConsole::print_(const char *text) { this->write_(text, strlen(text)); }

void RemoteConsole::printf_(const char *format, ...) {
  char buf[256];
  va_list args;
  va_start(args, format);
  const int n = vsnprintf(buf, sizeof(buf), format, args);
  va_end(args);
  if (n > 0)
    this->write_(buf, std::min<size_t>(n, sizeof(buf) - 1));
}

void RemoteConsole::prompt_() { this->print_("> "); }

void RemoteConsole::loop() {
  const uint32_t now = millis();
  if (now - this->last_poll_ < POLL_MS)
    return;
  this->last_poll_ = now;
  if (!this->enabled_)
    return;
  if (this->listener_ < 0) {
    if (now - this->last_open_try_ >= OPEN_RETRY_MS) {
      this->last_open_try_ = now;
      this->open_();
    }
    return;
  }
  this->accept_();
  if (this->client_ < 0)
    return;
  if (this->drop_pending_) {
    this->drop_client_("connection lost");
    return;
  }
  this->read_();
  if (this->client_ < 0)
    return;
#ifdef USE_REMOTE_CONSOLE_MODEM
  if (!this->at_wait_.empty() && static_cast<int32_t>(now - this->at_deadline_) >= 0) {
    this->at_wait_.clear();
    this->print_("no reply from the modem\r\n");
    this->prompt_();
  }
#endif
  if (now - this->last_activity_ >= this->idle_timeout_) {
    this->print_("idle, closing\r\n");
    this->drop_client_("idle");
  }
}

void RemoteConsole::read_() {
  char buf[64];
  const int n = lwip_recv(this->client_, buf, sizeof(buf), MSG_DONTWAIT);
  if (n == 0) {
    this->drop_client_("closed by the client");
    return;
  }
  if (n < 0) {
    if (errno != EAGAIN && errno != EWOULDBLOCK)
      this->drop_client_("connection lost");
    return;
  }
  this->last_activity_ = millis();
  for (int i = 0; i < n && this->client_ >= 0; i++) {
    const uint8_t c = buf[i];
    if (this->iac_skip_ > 0) {
      this->iac_skip_--;
    } else if (c == 0xFF) {
      this->iac_skip_ = 2;  // telnet option negotiation: ignored
    } else if (c == '\r' || c == '\n') {
      if (this->overflow_) {
        this->print_("line too long\r\n");
        this->prompt_();
      } else if (this->line_len_ > 0) {
        this->line_[this->line_len_] = '\0';
        this->handle_line_(this->line_);
      }
      this->line_len_ = 0;
      this->overflow_ = false;
    } else if (c == 0x08 || c == 0x7F) {
      if (this->line_len_ > 0)
        this->line_len_--;
    } else if (c >= 0x20 && c < 0x7F) {
      if (this->line_len_ < LINE_SIZE - 1) {
        this->line_[this->line_len_++] = c;
      } else {
        this->overflow_ = true;
      }
    }
  }
}

void RemoteConsole::handle_line_(char *line) {
  if (!this->authed_) {
    if (strcmp(line, this->password_) == 0) {
      this->authed_ = true;
      this->prompt_();
    } else if (++this->auth_failures_ >= MAX_AUTH_FAILURES) {
      this->drop_client_("wrong password");
    } else {
      this->print_("password: ");
    }
    return;
  }
  size_t len = strlen(line);
  while (len > 0 && line[len - 1] == ' ')
    line[--len] = '\0';
  const char *cmd = skip_spaces(line);
  if (*cmd == '\0') {
    this->prompt_();
    return;
  }
  // Command word in lower case, the argument as typed
  char word[8]{};
  size_t w = 0;
  while (cmd[w] != '\0' && cmd[w] != ' ' && w < sizeof(word) - 1) {
    word[w] = tolower(static_cast<unsigned char>(cmd[w]));
    w++;
  }
  const bool whole = cmd[w] == '\0' || cmd[w] == ' ';
  const char *arg = skip_spaces(cmd + w);

  if (whole && (strcmp(word, "help") == 0 || strcmp(word, "?") == 0)) {
    this->print_(HELP);
  } else if (whole && strcmp(word, "status") == 0) {
    this->cmd_status_();
  } else if (whole && strcmp(word, "log") == 0) {
    this->cmd_log_(arg);
  } else if (whole && (strcmp(word, "exit") == 0 || strcmp(word, "quit") == 0)) {
    this->print_("bye\r\n");
    this->drop_client_("exit");
    return;
  } else if (whole && strcmp(word, "reboot") == 0) {
    this->print_("restarting\r\n");
    this->drop_client_("reboot");
    App.safe_reboot();
    return;
#ifdef USE_REMOTE_CONSOLE_OBD2
  } else if (whole && strcmp(word, "obd") == 0) {
    this->cmd_obd_(arg);
    return;  // prompt after the answers
#endif
#ifdef USE_REMOTE_CONSOLE_MODEM
  } else if (whole && strcmp(word, "at") == 0 && *arg != '\0') {
    this->cmd_at_(arg);
    return;  // prompt after the reply
  } else if (word[0] == 'a' && word[1] == 't') {
    this->cmd_at_(cmd);  // "AT+CSQ" typed directly
    return;
#endif
  } else {
    this->print_("unknown command, try help\r\n");
  }
  this->prompt_();
}

void RemoteConsole::cmd_status_() {
  const uint32_t up = millis() / 1000;
  this->printf_("uptime      %ud %02u:%02u:%02u\r\n", static_cast<unsigned>(up / 86400),
                static_cast<unsigned>(up / 3600 % 24), static_cast<unsigned>(up / 60 % 60),
                static_cast<unsigned>(up % 60));
  this->printf_("reset       reason %d\r\n", static_cast<int>(esp_reset_reason()));
  this->printf_("heap        %u free, %u lowest (internal %u free)\r\n",
                static_cast<unsigned>(esp_get_free_heap_size()),
                static_cast<unsigned>(esp_get_minimum_free_heap_size()),
                static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)));
#ifdef USE_REMOTE_CONSOLE_MODEM
  this->printf_("modem       %s\r\n", this->modem_->is_connected() ? "connected" : "not connected");
#endif
#ifdef USE_REMOTE_CONSOLE_OBD2
  this->printf_("obd         %s\r\n", this->obd_->is_active() ? "active (engine running)" : "off");
#endif
  if (this->status_) {
    const std::string extra = this->status_();
    // The lambda writes plain "\n" lines
    size_t pos = 0;
    while (pos < extra.size()) {
      size_t end = extra.find('\n', pos);
      if (end == std::string::npos)
        end = extra.size();
      this->write_(extra.data() + pos, end - pos);
      this->print_("\r\n");
      pos = end + 1;
    }
  }
}

void RemoteConsole::cmd_log_(const char *arg) {
  if (strcasecmp(arg, "off") == 0) {
    this->log_level_ = 0;
  } else if (strcasecmp(arg, "error") == 0) {
    this->log_level_ = ESPHOME_LOG_LEVEL_ERROR;
  } else if (strcasecmp(arg, "warn") == 0) {
    this->log_level_ = ESPHOME_LOG_LEVEL_WARN;
  } else if (strcasecmp(arg, "info") == 0) {
    this->log_level_ = ESPHOME_LOG_LEVEL_CONFIG;
  } else if (strcasecmp(arg, "on") == 0 || strcasecmp(arg, "debug") == 0) {
    this->log_level_ = ESPHOME_LOG_LEVEL_VERY_VERBOSE;
  } else {
    this->print_("log on|off|error|warn|info|debug\r\n");
  }
}

void RemoteConsole::on_log_(uint8_t level, const char *tag, const char *message, size_t len) {
  if (this->client_ < 0 || !this->authed_)
    return;
#ifdef USE_REMOTE_CONSOLE_MODEM
  // The modem component logs every reply: "AT '<command>' -> OK: <reply>"
  if (!this->at_wait_.empty() && strcmp(tag, "modem") == 0) {
    const std::string line(message, len);
    const size_t at = line.find("AT '" + this->at_wait_ + "'");
    if (at != std::string::npos) {
      this->at_wait_.clear();
      size_t end = line.find('\033', at);  // colour reset at the end of the log line
      if (end == std::string::npos)
        end = line.size();
      this->write_(line.data() + at, end - at);
      this->print_("\r\n");
      this->prompt_();
    }
  }
#endif
  if (this->log_level_ == 0 || level > this->log_level_ || strcmp(tag, TAG) == 0)
    return;
  this->write_(message, len);
  this->print_("\r\n");
}

#ifdef USE_REMOTE_CONSOLE_OBD2
void RemoteConsole::cmd_obd_(const char *arg) {
  uint32_t tx_id = 0x7DF;
  uint8_t req[8];
  uint8_t n = 0;
  bool first = true;
  const char *p = arg;
  while (*p != '\0') {
    char *end;
    const unsigned long v = strtoul(p, &end, 16);
    const size_t digits = end - p;
    if (digits == 3 && first) {
      tx_id = v;  // three hex digits first: the address
    } else if (digits >= 1 && digits <= 2 && n < sizeof(req)) {
      req[n++] = v;
    } else {
      n = 0;
      break;
    }
    first = false;
    p = skip_spaces(end);
  }
  if (n == 0) {
    this->print_("obd [7E0..7E7] <1 to 7 hex bytes>, e.g. obd 01 0C\r\n");
    this->prompt_();
    return;
  }
  this->obd_answers_ = 0;
  const char *refused =
      this->obd_->raw_request(tx_id, req, n, [this](uint32_t can_id, const uint8_t *data, uint16_t len, bool done) {
        if (done) {
          if (this->obd_answers_ == 0)
            this->print_("no answer\r\n");
          this->prompt_();
          return;
        }
        this->obd_answers_++;
        char line[48 + 3 * 128];
        int pos = snprintf(line, sizeof(line), "%03X:", static_cast<unsigned>(can_id));
        for (uint16_t i = 0; i < len && i < 128; i++)
          pos += snprintf(line + pos, sizeof(line) - pos, " %02X", data[i]);
        if (len >= 3 && data[0] == 0x7F)
          pos += snprintf(line + pos, sizeof(line) - pos, "  (refused, NRC 0x%02X)", data[2]);
        this->write_(line, pos);
        this->print_("\r\n");
      });
  if (refused != nullptr) {
    this->printf_("%s\r\n", refused);
    this->prompt_();
  }
}
#endif

#ifdef USE_REMOTE_CONSOLE_MODEM
void RemoteConsole::cmd_at_(const char *command) {
  std::string upper;
  for (const char *p = command; *p != '\0'; p++)
    upper += toupper(static_cast<unsigned char>(*p));
  if (upper.rfind("AT", 0) != 0) {
    this->print_("modem commands start with AT\r\n");
    this->prompt_();
    return;
  }
  for (const char *blocked : AT_BLOCKED) {
    // "ATD" and the like only at the start, "+IPR" and the like anywhere
    const bool hit = blocked[0] == 'A' ? upper.rfind(blocked, 0) == 0 : upper.find(blocked) != std::string::npos;
    if (hit) {
      this->printf_("%s is not allowed from the console\r\n", blocked);
      this->prompt_();
      return;
    }
  }
  if (!this->at_wait_.empty() || !this->modem_->send_at(command, AT_TIMEOUT_MS)) {
    this->print_("modem busy or not ready, try again\r\n");
    this->prompt_();
    return;
  }
  this->at_wait_ = command;
  this->at_deadline_ = millis() + AT_TIMEOUT_MS + 2000;
}
#endif

}  // namespace esphome::remote_console
