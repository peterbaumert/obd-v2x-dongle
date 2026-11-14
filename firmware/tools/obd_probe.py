"""Read-only OBD/UDS probe for a WiCAN (or any ELM327 over TCP), run from a laptop.

Finds out what the car answers before anything goes into the dongle firmware. It only ever sends read services
(01 PIDs, 21/22 reads, 1A identification, 3E tester present, 10 01/10 03 sessions); everything else is refused,
so it cannot code, reset or clear anything.

Setup: WiCAN web UI -> Protocol "ELM327", port type TCP (note the port). Join the WiCAN's Wi-Fi (default AP
192.168.80.1) or put it on your network. Engine running (the script checks RPM; --no-engine-check for ignition-only).
ELM327 mode only sees response IDs 7E8..7EF. --slcan (WiCAN Protocol "SLCAN", raw CAN, the script does ISO-TP itself)
reaches any response ID, but only for known request/response pairs: find-ecus is disabled there, because a tester
present sweep over raw CAN made a W205 start a Mercedes service call (a module took one frame for a button press).

Step-by-step test order: firmware/README.md, "Testing the car with a WiCAN".

    python firmware/tools/obd_probe.py [--host 192.168.80.1] [--port 3333] <command> ...

    standard                      which mode-01 PIDs each ECU supports, then one decoded read of each
    mercedes                      OBDb C-Class candidates: odometer, oil temp, fuel litres, gear, ATF temp, ...
    find-ecus [--from 400 --to 7FF]
                                  tester present (3E 00) to every 11-bit request ID, lists who answers
    dids --tx 7E0 --rx 7E8 [--from F100 --to F1FF] [--extended] [--out scan.json]
                                  22 xxxx over a DID range on one ECU, keeps everything that is not "out of range"
    watch --tx .. --rx .. (--dids 2001,2002 | --scan scan.json) [--interval 0.5]
                                  polls DIDs and prints only bytes that change: open/close a door, lock, etc.
    sniff                         LISTEN ONLY (WiCAN Protocol SLCAN, opened silent): records all bus traffic with
                                  timestamps, sends nothing; Enter (+ optional note) = numbered mark, q + Enter = stop
    diff a.json b.json            byte differences between two scans (scan, change something, scan again)
    raw --tx 7E0 --rx 7E8 22016B  one request (read services only)

Every session is logged raw to firmware/tools/probe-logs/ (git-ignored). VINs are masked on screen and in scan
files, but the raw .log keeps the bytes (a VIN is split across CAN frames there): don't share raw logs unedited.
"""
import argparse
import atexit
import datetime
import json
import pathlib
import re
import socket
import sys
import threading
import time

LOG_DIR = pathlib.Path(__file__).resolve().parent / 'probe-logs'

NRC = {0x10: 'generalReject', 0x11: 'serviceNotSupported', 0x12: 'subFunctionNotSupported',
       0x13: 'incorrectLength', 0x14: 'responseTooLong', 0x21: 'busyRepeatRequest', 0x22: 'conditionsNotCorrect',
       0x24: 'requestSequenceError', 0x31: 'requestOutOfRange', 0x33: 'securityAccessDenied',
       0x78: 'responsePending', 0x7E: 'subFunctionNotSupportedInActiveSession',
       0x7F: 'serviceNotSupportedInActiveSession'}

VIN_RE = re.compile(r'[A-HJ-NPR-Z0-9]{17}')


def mask_vin(text):
    return VIN_RE.sub(lambda m: m.group(0)[:3] + '*' * 14, text)


def mask_payload(data):
    """Replace VIN characters inside a response with '*' (keeps the first 3, the manufacturer code)."""
    m = VIN_RE.search(data.decode('latin-1'))
    if not m:
        return data
    return data[:m.start() + 3] + b'*' * 14 + data[m.end():]


def ascii_of(data):
    return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)


def is_read_only(req):
    """Whitelist of services this tool may send."""
    sid = req[0]
    if sid in (0x01, 0x21, 0x22, 0x1A):
        return True
    if sid == 0x3E:
        return len(req) == 2 and req[1] in (0x00, 0x80)
    if sid == 0x10:
        return len(req) == 2 and req[1] in (0x01, 0x03)  # default / extended session only
    return False


class Log:
    def __init__(self, name):
        LOG_DIR.mkdir(exist_ok=True)
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        self.path = LOG_DIR / f'{stamp}-{name}.log'
        self.f = self.path.open('w', encoding='utf-8')
        self.t0 = self.last_flush = time.time()
        self.lock = threading.Lock()
        atexit.register(self.close)

    def write(self, line):
        """Line with seconds since start; flushed at most twice a second (sniff logs many frames)."""
        with self.lock:
            now = time.time()
            self.f.write(f'{now - self.t0:9.3f} {mask_vin(line)}\n')
            if now - self.last_flush > 0.5:
                self.f.flush()
                self.last_flush = now

    def close(self):
        with self.lock:
            self.f.flush()


class Elm:
    def __init__(self, host, port, log):
        self.log = log
        self.sock = socket.create_connection((host, port), timeout=5)
        self.buf = b''
        self.state = {}

    def cmd(self, text, timeout=3.0):
        self.log.write(f'> {text}')
        self.sock.sendall(text.encode() + b'\r')
        end = time.time() + timeout
        while b'>' not in self.buf:
            self.sock.settimeout(max(0.05, end - time.time()))
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                raise ConnectionError('adapter closed the connection')
            self.buf += chunk
            if time.time() > end:
                break
        out, _, self.buf = self.buf.partition(b'>')
        lines = [l.strip() for l in out.decode(errors='replace').replace('\n', '\r').split('\r')]
        lines = [l for l in lines if l and l != text and l != 'SEARCHING...']
        for l in lines:
            self.log.write(f'< {l}')
        return lines

    def at(self, text, timeout=3.0):
        """AT command, skipped when the setting is already active."""
        key = re.match(r'AT(SH|CRA|FCSH|FCSD|FCSM|ST)', text)
        if key and self.state.get(key.group(1)) == text:
            return ['OK']
        r = self.cmd(text, timeout)
        if key:
            self.state[key.group(1)] = text
        return r

    def init(self):
        self.cmd('ATZ', timeout=5)
        for c in ('ATE0', 'ATL0', 'ATS1', 'ATH1', 'ATSP6'):
            self.cmd(c)
        self.timeout_ms(200)

    def describe(self):
        return ' '.join(self.cmd('ATI')) + ', battery ' + ' '.join(self.cmd('ATRV'))

    def timeout_ms(self, ms):
        self.at(f'ATST{max(1, min(255, ms // 4)):02X}')

    def target(self, tx, rx=None):
        """Address one ECU (tx = request ID, rx = response ID; None = accept any response ID)."""
        self.at(f'ATSH{tx:03X}')
        if rx is None or (0x7E8 <= rx <= 0x7EF and (tx == 0x7DF or tx == rx - 8)):
            # OBD IDs: the adapter's default filter (7E8..7EF) and automatic flow control already fit.
            # Explicit ATCRA/ATFCSM settings here made a WiCAN miss the engine ECU's answers.
            self.at('ATCRA')
            self.at('ATFCSM0')
        else:
            self.at(f'ATCRA{rx:03X}')
            self.at(f'ATFCSH{tx:03X}')
            self.at('ATFCSD300000')
            self.at('ATFCSM1')

    def request(self, req, timeout=3.0):
        """Send one request (bytes); returns ({rx_id: [payload, ...]}, raw lines)."""
        if not is_read_only(req):
            raise ValueError(f'refusing non-read service: {req.hex(" ").upper()}')
        lines = self.cmd(req.hex().upper(), timeout)
        msgs = {cid: [mask_payload(m) for m in ms] for cid, ms in parse_frames(lines).items()}
        return msgs, lines


class Slcan:
    """Same interface as Elm, but over SLCAN (WiCAN protocol "SLCAN"): raw CAN frames, no adapter filter, so ECUs
    with any response ID are visible. ISO-TP (single/first/consecutive frames, flow control) is done here."""

    def __init__(self, host, port, log):
        self.log = log
        self.sock = socket.create_connection((host, port), timeout=5)
        self.buf = b''
        self.tx, self.rx = 0x7DF, None
        self.timeout = 0.2

    def _send(self, text, log=True):
        if log:
            self.log.write(f'> {text}')
        self.sock.sendall(text.encode() + b'\r')  # one command per write: WiCAN parses per packet

    def _frames(self, until):
        """Received standard frames (id, data) until the deadline (or until one arrives)."""
        while True:
            while b'\r' in self.buf:
                line, _, self.buf = self.buf.partition(b'\r')
                line = line.decode(errors='replace').strip()
                if len(line) >= 5 and line[0] == 't':
                    try:
                        cid, dlc = int(line[1:4], 16), int(line[4], 16)
                        data = bytes.fromhex(line[5:5 + 2 * dlc])
                    except ValueError:
                        continue
                    self.log.write(f'< {cid:03X} {data.hex(" ").upper()}')
                    return cid, data
            left = until - time.time()
            if left <= 0:
                return None
            self.sock.settimeout(left)
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                return None
            if not chunk:
                raise ConnectionError('adapter closed the connection')
            self.buf += chunk

    def _drain(self):
        while self._frames(time.time() + 0.02):
            pass

    def _send_frame(self, cid, data):
        data = data + b'\xAA' * (8 - len(data))
        self.log.write(f'> {cid:03X} {data.hex(" ").upper()}')  # spaced, so the VIN mask can't hide it
        self._send(f't{cid:03X}8{data.hex().upper()}', log=False)

    def init(self):
        for c in ('C', 'S6', 'O'):  # close, 500 kbit/s, open (normal mode, frames are acknowledged)
            self._send(c)
            time.sleep(0.2)
        self._drain()

    def describe(self):
        return 'SLCAN (raw CAN, 500 kbit/s)'

    def timeout_ms(self, ms):
        self.timeout = ms / 1000

    def target(self, tx, rx=None):
        self.tx, self.rx = tx, rx

    def request(self, req, timeout=3.0):
        if not is_read_only(req):
            raise ValueError(f'refusing non-read service: {req.hex(" ").upper()}')
        if len(req) > 7:
            raise ValueError('requests longer than 7 bytes are not supported')
        self._drain()
        self._send_frame(self.tx, bytes([len(req)]) + req)
        start = time.time()
        end, hard_end = start + self.timeout, start + max(timeout, 5.0)
        lines, multi, ok = [], set(), (req[0] + 0x40, 0x7F)
        while True:
            f = self._frames(min(end, hard_end))
            if f is None:
                break
            cid, data = f
            if cid == self.tx or (self.rx is not None and cid != self.rx) or len(data) < 2:
                continue
            # only frames that can be an answer to this request (the bus may carry other traffic)
            pci = data[0] >> 4
            if pci == 0:
                if not (1 <= (data[0] & 0x0F) <= 7 and data[1] in ok):
                    continue
            elif pci == 1:
                if len(data) < 3 or data[2] not in ok:
                    continue
                multi.add(cid)
            elif not (pci == 2 and cid in multi):
                continue
            lines.append(f'{cid:03X} ' + data.hex(' ').upper())
            if pci == 1:
                self._send_frame(self.tx, b'\x30\x00\x00')  # flow control: send everything, no gap
            pending = pci == 0 and len(data) >= 4 and data[1] == 0x7F and data[3] == 0x78
            end = time.time() + (5.0 if pending else self.timeout)
        msgs = {cid: [mask_payload(m) for m in ms] for cid, ms in parse_frames(lines).items()}
        return msgs, lines


def parse_frames(lines):
    """ELM327 'ATH1 ATS1' output -> ISO-TP reassembled payloads per CAN ID."""
    frames = {}
    for l in lines:
        tok = l.split()
        if len(tok) < 2 or len(tok[0]) != 3 or not all(re.fullmatch(r'[0-9A-Fa-f]{2}', t) for t in tok[1:]):
            continue
        frames.setdefault(int(tok[0], 16), []).append(bytes(int(t, 16) for t in tok[1:]))
    msgs = {}
    for cid, fl in frames.items():
        out, cur, need = [], None, 0
        for f in fl:
            pci = f[0] >> 4
            if pci == 0 and 0 < (f[0] & 0x0F) <= len(f) - 1:
                out.append(f[1:1 + (f[0] & 0x0F)])
            elif pci == 1 and len(f) >= 2:
                need = ((f[0] & 0x0F) << 8) | f[1]
                cur = bytearray(f[2:])
            elif pci == 2 and cur is not None:
                cur += f[1:]
                if len(cur) >= need:
                    out.append(bytes(cur[:need]))
                    cur = None
            else:  # adapter already stripped the PCI byte
                out.append(f)
        if cur is not None:
            out.append(bytes(cur))  # incomplete multi-frame, keep what came
        msgs[cid] = out
    return msgs


def final(msgs):
    """Last message per ECU that is not 'response pending'."""
    res = {}
    for cid, ms in msgs.items():
        ms = [m for m in ms if not (len(m) >= 3 and m[0] == 0x7F and m[2] == 0x78)]
        if ms:
            res[cid] = ms[-1]
    return res


def describe(payload):
    if len(payload) >= 3 and payload[0] == 0x7F:
        return f'NEGATIVE {payload[2]:02X} {NRC.get(payload[2], "?")}'
    return f'{payload.hex(" ").upper()}  |{ascii_of(payload)}|'


def show(text):
    print(mask_vin(text), flush=True)


# --------------------------------------------------------------------------- engine check

def engine_check(elm, args):
    if args.no_engine_check:
        return
    elm.target(0x7DF)
    res = final(elm.request(bytes([0x01, 0x0C]))[0])
    rpm = next(((p[2] * 256 + p[3]) / 4 for p in res.values() if len(p) >= 4 and p[0] == 0x41), None)
    if rpm is None or rpm < 300:
        sys.exit(f'Engine not running (RPM: {rpm}). Start it, or pass --no-engine-check for an ignition-only test.')
    show(f'Engine running, {rpm:.0f} rpm')


# --------------------------------------------------------------------------- standard (mode 01)

def u16(d):
    return d[0] * 256 + d[1]


PID01 = {
    0x04: ('engine load', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x05: ('coolant', lambda d: f'{d[0] - 40} C'),
    0x06: ('short fuel trim B1', lambda d: f'{(d[0] - 128) * 100 / 128:.1f} %'),
    0x07: ('long fuel trim B1', lambda d: f'{(d[0] - 128) * 100 / 128:.1f} %'),
    0x0B: ('manifold pressure', lambda d: f'{d[0]} kPa'),
    0x0C: ('rpm', lambda d: f'{u16(d) / 4:.0f} rpm'),
    0x0D: ('speed', lambda d: f'{d[0]} km/h'),
    0x0E: ('timing advance', lambda d: f'{d[0] / 2 - 64:.1f} deg'),
    0x0F: ('intake air', lambda d: f'{d[0] - 40} C'),
    0x10: ('MAF', lambda d: f'{u16(d) / 100:.2f} g/s'),
    0x11: ('throttle', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x1F: ('run time', lambda d: f'{u16(d)} s'),
    0x21: ('km with MIL on', lambda d: f'{u16(d)} km'),
    0x23: ('fuel rail pressure', lambda d: f'{u16(d) * 10} kPa'),
    0x2E: ('EVAP purge', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x2F: ('fuel level', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x30: ('warm-ups since clear', lambda d: f'{d[0]}'),
    0x31: ('km since codes cleared', lambda d: f'{u16(d)} km'),
    0x33: ('barometric', lambda d: f'{d[0]} kPa'),
    0x3C: ('catalyst temp B1S1', lambda d: f'{u16(d) / 10 - 40:.0f} C'),
    0x42: ('module voltage', lambda d: f'{u16(d) / 1000:.2f} V'),
    0x43: ('absolute load', lambda d: f'{u16(d) * 100 / 255:.1f} %'),
    0x44: ('commanded lambda', lambda d: f'{u16(d) / 32768:.3f}'),
    0x45: ('relative throttle', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x46: ('ambient', lambda d: f'{d[0] - 40} C'),
    0x49: ('pedal D', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x4A: ('pedal E', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x4C: ('throttle actuator', lambda d: f'{d[0] * 100 / 255:.1f} %'),
    0x51: ('fuel type', lambda d: {1: 'petrol', 4: 'diesel'}.get(d[0], str(d[0]))),
    0x5C: ('oil temp', lambda d: f'{d[0] - 40} C'),
    0x5E: ('fuel rate', lambda d: f'{u16(d) / 20:.2f} L/h'),
    0xA6: ('odometer', lambda d: f'{int.from_bytes(d[:4], "big") / 10:.1f} km'),
}


def cmd_standard(elm, args):
    elm.target(0x7DF)
    support = {}
    for base in range(0x00, 0xE0, 0x20):
        res = final(elm.request(bytes([0x01, base]))[0])
        any_next = False
        for cid, p in res.items():
            if len(p) >= 6 and p[0] == 0x41 and p[1] == base:
                bits = int.from_bytes(p[2:6], 'big')
                for i in range(32):
                    if bits & (1 << (31 - i)):
                        support.setdefault(cid, set()).add(base + i + 1)
                any_next |= bool(bits & 1)
        if not any_next:
            break
    if not support:
        sys.exit('No ECU answered 01 00.')
    for cid in sorted(support):
        pids = sorted(p for p in support[cid] if p % 0x20)
        show(f'\nECU {cid:03X} supports: ' + ' '.join(f'{p:02X}' for p in pids))
        # stay on the functional address 7DF and pick this ECU's answer: the W205 engine ECU answers mode 01
        # only there, not physically on 7E0
        for pid in pids:
            res = final(elm.request(bytes([0x01, pid]))[0]).get(cid)
            name, fn = PID01.get(pid, (f'PID {pid:02X}', None))
            if res is None:
                val = 'no answer'
            elif res[0] == 0x41 and fn:
                try:
                    val = fn(res[2:])
                except IndexError:
                    val = describe(res)
            else:
                val = describe(res)
            show(f'  01 {pid:02X}  {name:24} {val}')


# --------------------------------------------------------------------------- mercedes (OBDb C-Class signalset)

def f2c(f):
    return (f - 32) * 5 / 9


# (tx, rx, request, [(name, bix, len, mul, div, add, signed, unit, convert)])  bix/len in bits after the echo
MERCEDES = [
    (0x7E0, 0x7E8, '22016B', [('odometer', 288, 16, 2, 1, 0, False, 'km', None)]),
    (0x7E0, 0x7E8, '222030', [('fuel in tank', 0, 16, 0.099934824, 1, 0, False, 'L', None)]),
    (0x7E0, 0x7E8, '222095', [('engine oil temp', 0, 8, 27, 20, -54, False, 'C', f2c)]),
    (0x7E0, 0x7E8, '222017', [('radiator temp', 0, 16, 27, 32, 32, False, 'C', f2c)]),
    (0x7E0, 0x7E8, '222071', [('fuel rail pressure', 0, 16, 0.4998701, 1, 0, False, 'kPa', None)]),
    (0x7E0, 0x7E8, '22016F', [('fuel temp', 128, 16, 1, 10, -273, False, 'C', None)]),
    (0x7E0, 0x7E8, '220163', [('boost air temp', 48, 16, 1, 10, -273.1, False, 'C', None),
                              ('boost pressure (raw)', 120, 16, 1, 1, 0, True, '', None)]),
    (0x7E0, 0x7E8, '220168', [('exhaust back pressure (raw)', 0, 16, 1, 1, 0, True, '', None),
                              ('DPF diff pressure (raw)', 320, 16, 1, 1, 0, True, '', None)]),
    (0x7E1, 0x7E9, '2130', [('converter slip', 8, 8, 1, 1, 0, False, 'rpm', None),
                            ('current gear', 80, 8, 1, 1, 0, False, '', None),
                            ('ATF temp v1', 88, 8, 9, 5, -58, False, 'C', f2c)]),
    (0x7E1, 0x7E9, '2134', [('ATF temp v3', 72, 16, 1, 10, 0, True, 'C', None)]),
    (0x7E1, 0x7E9, '220230', [('ATF temp v2', 88, 8, 9, 5, -58, False, 'C', f2c)]),
    (0x7E1, 0x7E9, '220234', [('ATF temp v4', 24, 8, 1, 1, -50, False, 'C', None)]),
    (0x7E2, 0x7EA, '222001', [('wheel speed FL', 0, 16, 1, 100, 0, False, 'km/h', None)]),
    (0x7E2, 0x7EA, '222002', [('steering angle', 72, 16, 1, 10, 0, True, 'deg', None)]),
]


def bits(data, bix, length, signed):
    total = len(data) * 8
    if bix + length > total:
        return None
    v = (int.from_bytes(data, 'big') >> (total - bix - length)) & ((1 << length) - 1)
    if signed and v & (1 << (length - 1)):
        v -= 1 << length
    return v


def cmd_mercedes(elm, args):
    for tx, rx, req, sigs in MERCEDES:
        elm.target(tx, rx)
        res = final(elm.request(bytes.fromhex(req))[0]).get(rx)
        show(f'\n{tx:03X} {req}: ' + ('no answer' if res is None else describe(res)))
        if res is None or res[0] != bytes.fromhex(req)[0] + 0x40:
            continue
        data = res[len(req) // 2:]  # strip service + DID/local id echo
        for name, bix, ln, mul, div, add, signed, unit, conv in sigs:
            v = bits(data, bix, ln, signed)
            if v is None:
                show(f'    {name:28} answer too short ({len(data)} data bytes)')
                continue
            val = v * mul / div + add
            if conv:
                val = conv(val)
            show(f'    {name:28} {val:.1f} {unit}   (raw {v})')


# --------------------------------------------------------------------------- ECU discovery

def cmd_find_ecus(elm, args):
    lo, hi = int(args.lo, 16), int(args.hi, 16)
    # Tester present to arbitrary IDs is not harmless: on a W205 a SLCAN sweep made a module act on one of the
    # frames as if it were a normal message (it started a Mercedes service call). So: no sweep over raw CAN,
    # and never below 400 (normal function messages live there).
    if isinstance(elm, Slcan):
        raise ValueError('find-ecus is disabled in SLCAN mode: a sweep over raw CAN triggered a car function. '
                         'Use dids/raw/watch with known --tx/--rx IDs instead.')
    if lo < 0x400:
        raise ValueError('find-ecus refuses request IDs below 400 (normal function messages live there).')
    elm.timeout_ms(args.timeout)
    found = {}
    show(f'Tester present to {lo:03X}..{hi:03X}, any response ID accepted ...')
    for tx in range(lo, hi + 1):
        if tx == 0x7DF:
            continue
        elm.target(tx)
        msgs = final(elm.request(bytes([0x3E, 0x00]), timeout=1.0)[0])
        for rx, p in msgs.items():
            if p[:1] == b'\x7E' or p[:2] == b'\x7F\x3E':
                found.setdefault(tx, []).append(rx)
                show(f'  request {tx:03X} -> response {rx:03X}: {describe(p)}')
        if tx % 0x40 == 0x3F:
            print(f'  ... {tx:03X}', file=sys.stderr)
    elm.timeout_ms(200)
    show(f'\n{len(found)} ECU(s) answered.')
    show('ELM327 mode only sees response IDs 7E8..7EF (a WiCAN has no wildcard filter).')
    for tx, rxs in sorted(found.items()):
        for rx in rxs:
            elm.target(tx, rx)
            for req in ('22F187', '22F150', '1A86'):  # part number, hw version, KWP ident
                p = final(elm.request(bytes.fromhex(req))[0]).get(rx)
                if p is not None and p[0] != 0x7F:
                    show(f'  {tx:03X}/{rx:03X} {req}: {describe(p)}')
                    break


# --------------------------------------------------------------------------- DID scan / watch / diff

def keep_alive(elm, last):
    if time.time() - last > 2.0:
        elm.request(bytes([0x3E, 0x00]))
        return time.time()
    return last


def cmd_dids(elm, args):
    tx, rx = int(args.tx, 16), int(args.rx, 16)
    lo, hi = int(args.lo, 16), int(args.hi, 16)
    elm.target(tx, rx)
    elm.timeout_ms(args.timeout)
    last = time.time()
    if args.extended:
        show('Extended session: ' + describe(final(elm.request(bytes([0x10, 0x03]))[0]).get(rx, b'')))
    result = {}
    try:
        for did in range(lo, hi + 1):
            if args.extended:
                last = keep_alive(elm, last)
            p = final(elm.request(bytes([0x22, did >> 8, did & 0xFF]))[0]).get(rx)
            if p is None:
                continue
            if p[0] == 0x7F and p[2] in (0x31, 0x11, 0x12):
                continue
            result[f'{did:04X}'] = p.hex().upper()
            show(f'  22 {did:04X}: {describe(p)}')
            if did % 0x100 == 0xFF:
                print(f'  ... {did:04X}', file=sys.stderr)
    except KeyboardInterrupt:
        show('interrupted, saving what was found')
    finally:
        if args.extended:
            elm.request(bytes([0x10, 0x01]))
        elm.timeout_ms(200)
    out = pathlib.Path(args.out) if args.out else LOG_DIR / f'scan-{tx:03X}-{lo:04X}-{hi:04X}-{int(time.time())}.json'
    out.write_text(json.dumps({'tx': f'{tx:03X}', 'rx': f'{rx:03X}', 'dids': result}, indent=1))
    show(f'\n{len(result)} DIDs answered, saved to {out}')


def byte_diff(a, b):
    a, b = bytes.fromhex(a), bytes.fromhex(b)
    out = []
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else None
        y = b[i] if i < len(b) else None
        if x != y:
            fmt = lambda v: '--' if v is None else f'{v:02X}'
            bitinfo = f' bits {x ^ y:08b}' if x is not None and y is not None else ''
            out.append(f'byte {i}: {fmt(x)} -> {fmt(y)}{bitinfo}')
    return out


def cmd_diff(_elm, args):
    a = json.loads(pathlib.Path(args.a).read_text())['dids']
    b = json.loads(pathlib.Path(args.b).read_text())['dids']
    for did in sorted(set(a) | set(b)):
        if a.get(did) != b.get(did):
            if did not in a or did not in b:
                print(f'22 {did}: only in {"b" if did not in a else "a"}')
                continue
            print(f'22 {did}: ' + '; '.join(byte_diff(a[did], b[did])))


def cmd_watch(elm, args):
    if args.scan:
        scan = json.loads(pathlib.Path(args.scan).read_text())
        tx, rx = int(scan['tx'], 16), int(scan['rx'], 16)
        dids = [d for d, p in scan['dids'].items() if not p.startswith('7F')]
    else:
        tx, rx = int(args.tx, 16), int(args.rx, 16)
        dids = [d.strip().upper() for d in args.dids.split(',')]
    elm.target(tx, rx)
    last_ka = time.time()
    if args.extended:
        elm.request(bytes([0x10, 0x03]))
    prev = {}
    show(f'Watching {len(dids)} DIDs on {tx:03X}. Change things in the car now; Ctrl+C to stop.')
    try:
        while True:
            for did in dids:
                if args.extended:
                    last_ka = keep_alive(elm, last_ka)
                p = final(elm.request(bytes.fromhex('22' + did))[0]).get(rx)
                cur = p.hex().upper() if p is not None else ''
                if did in prev and prev[did] != cur and prev[did] and cur:
                    t = datetime.datetime.now().strftime('%H:%M:%S')
                    msg = f'{t} 22 {did}: ' + '; '.join(byte_diff(prev[did], cur))
                    show(msg)
                    elm.log.write('CHANGE ' + msg)
                prev[did] = cur
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if args.extended:
            elm.request(bytes([0x10, 0x01]))


def cmd_raw(elm, args):
    tx, rx = int(args.tx, 16), int(args.rx, 16) if args.rx else None
    elm.target(tx, rx)
    msgs, _ = elm.request(bytes.fromhex(args.request))
    for cid, ms in msgs.items():
        for m in ms:
            show(f'{cid:03X}: {describe(m)}')
    if not msgs:
        show('no answer')


# --------------------------------------------------------------------------- sniff (listen only)

def cmd_sniff(args):
    """Record all bus traffic with the WiCAN in SLCAN listen-only mode: nothing is sent to the car, frames are not
    even acknowledged. Enter (optionally with a note) writes a numbered MARK into the log."""
    log = Log('sniff')
    print(f'log: {log.path}', file=sys.stderr)
    try:
        bus = Slcan(args.host, args.port, log)
    except OSError as e:
        sys.exit(f'Cannot reach {args.host}:{args.port} ({e}). WiCAN in SLCAN mode (TCP) and on this Wi-Fi?')
    for c in ('C', 'S6', 'L'):  # close, 500 kbit/s, open LISTEN-ONLY (silent: no ACK, no transmit)
        bus._send(c)
        time.sleep(0.2)
    marks, stop = [0], threading.Event()

    def read_marks():
        while True:
            try:
                note = input()
            except (EOFError, OSError):
                return
            if note.strip().lower() == 'q':
                stop.set()
                return
            marks[0] += 1
            log.write(f'MARK {marks[0]} {note.strip()}')
            print(f'  MARK {marks[0]} {note.strip()}', flush=True)

    threading.Thread(target=read_marks, daemon=True).start()
    show('Listening only (nothing is sent). Press Enter at each action, optionally type a note first '
         '(e.g. "driver door open"). q + Enter (or Ctrl+C) to stop.')
    count, ids, last = 0, set(), time.time()
    try:
        while not stop.is_set():
            f = bus._frames(time.time() + 1.0)  # logs every frame with its time
            if f:
                count += 1
                ids.add(f[0])
            if time.time() - last > 10:
                print(f'  {count} frames, {len(ids)} IDs, {marks[0]} marks', file=sys.stderr, flush=True)
                last = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bus._send('C')
        except OSError:
            pass
        log.close()
    show(f'\n{count} frames from {len(ids)} IDs, {marks[0]} marks. Log: {log.path}')


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='192.168.80.1')
    ap.add_argument('--port', type=int, default=3333)
    ap.add_argument('--no-engine-check', action='store_true', help='allow running with the engine off')
    ap.add_argument('--slcan', action='store_true',
                    help='talk SLCAN (WiCAN Protocol "SLCAN") instead of ELM327: sees every response ID')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('standard')
    sub.add_parser('mercedes')
    p = sub.add_parser('find-ecus')
    p.add_argument('--from', dest='lo', default='400')
    p.add_argument('--to', dest='hi', default='7FF')
    p.add_argument('--timeout', type=int, default=60, help='answer timeout per ID in ms')
    p = sub.add_parser('dids')
    p.add_argument('--tx', required=True)
    p.add_argument('--rx', required=True)
    p.add_argument('--from', dest='lo', default='F100')
    p.add_argument('--to', dest='hi', default='F1FF')
    p.add_argument('--extended', action='store_true', help='switch to extended session (10 03) first')
    p.add_argument('--timeout', type=int, default=100, help='answer timeout per DID in ms')
    p.add_argument('--out')
    p = sub.add_parser('watch')
    p.add_argument('--tx')
    p.add_argument('--rx')
    p.add_argument('--dids', help='comma separated, e.g. 2001,2002')
    p.add_argument('--scan', help='watch every DID that answered in this dids scan file')
    p.add_argument('--extended', action='store_true')
    p.add_argument('--interval', type=float, default=0.3)
    sub.add_parser('sniff', help='listen only (WiCAN Protocol SLCAN): record all bus traffic, Enter = mark')
    p = sub.add_parser('diff')
    p.add_argument('a')
    p.add_argument('b')
    p = sub.add_parser('raw')
    p.add_argument('--tx', required=True)
    p.add_argument('--rx')
    p.add_argument('request')
    args = ap.parse_args()

    if args.cmd == 'diff':
        return cmd_diff(None, args)
    if args.cmd == 'sniff':
        return cmd_sniff(args)  # always SLCAN listen-only, no engine check (that would send a request)
    if args.cmd == 'watch' and not args.scan and not (args.tx and args.rx and args.dids):
        ap.error('watch needs --scan FILE or --tx, --rx and --dids')

    log = Log(args.cmd)
    print(f'log: {log.path}', file=sys.stderr)
    mode = 'SLCAN' if args.slcan else 'ELM327'
    try:
        elm = (Slcan if args.slcan else Elm)(args.host, args.port, log)
    except OSError as e:
        sys.exit(f'Cannot reach {args.host}:{args.port} ({e}). WiCAN in {mode} mode (TCP) and on this Wi-Fi?')
    elm.init()
    show('Adapter: ' + elm.describe())
    engine_check(elm, args)
    try:
        {'standard': cmd_standard, 'mercedes': cmd_mercedes, 'find-ecus': cmd_find_ecus, 'dids': cmd_dids,
         'watch': cmd_watch, 'raw': cmd_raw}[args.cmd](elm, args)
    except ValueError as e:
        sys.exit(str(e))


if __name__ == '__main__':
    main()
