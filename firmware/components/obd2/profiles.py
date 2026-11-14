"""Vehicle profiles (firmware/vehicles/*.json, format in vehicles/README.md) for the passive CAN signals.

Every profile in the `vehicles` folder next to the YAML is compiled into the firmware; the active one is chosen at
runtime (select `vehicle_profile`). Entities are declared per signal name (sensor / binary_sensor / text_sensor
`signals:`); a signal's kind decides which platform it can use:
  number -> sensor, flag -> binary_sensor, enum -> text_sensor (and binary_sensor if the enum names an "on" state).
"""
from dataclasses import dataclass, field
import json
from pathlib import Path

import esphome.config_validation as cv
from esphome.core import CORE

PROFILE_DIR = "vehicles"
KIND_NUMBER, KIND_FLAG, KIND_ENUM = "number", "flag", "enum"
UNITS = {"celsius": "°C", "kilometers": "km", "liters": "L"}


@dataclass
class Signal:
    name: str
    kind: str
    can_id: int
    start: int
    length: int = 1
    little: bool = False
    mask: int = 0
    scale: float = 1.0
    offset: float = 0.0
    unit: str | None = None
    invalid: list[int] = field(default_factory=list)
    values: list[tuple[int, str]] = field(default_factory=list)
    on: str | None = None


@dataclass
class Profile:
    id: str
    title: str
    signals: list[Signal]


def _int(v):
    return int(v, 0) if isinstance(v, str) else int(v)


def _parse_signal(path, s):
    name = s.get("name")
    if not name or "id" not in s or "start_byte" not in s:
        raise cv.Invalid(f"{path}: every signal needs name, id and start_byte ({s})")
    kind = KIND_ENUM if "values" in s else KIND_FLAG if "mask" in s else KIND_NUMBER
    sig = Signal(name=name, kind=kind, can_id=_int(s["id"]), start=int(s["start_byte"]),
                 length=int(s.get("length", 1)), little=s.get("byte_order", "big") == "little",
                 mask=_int(s.get("mask", 0)), scale=float(s.get("scale", 1)), offset=float(s.get("offset", 0)),
                 unit=s.get("unit"), invalid=[_int(x) for x in s.get("invalid", [])],
                 values=[(_int(k), v) for k, v in s.get("values", {}).items()], on=s.get("on"))
    if not 0 < sig.can_id < 0x800:
        raise cv.Invalid(f"{path}: {name}: only 11-bit CAN IDs are supported")
    if sig.kind != KIND_FLAG and not 1 <= sig.length <= 4:
        raise cv.Invalid(f"{path}: {name}: length must be 1..4 bytes")
    if sig.start + (1 if sig.kind == KIND_FLAG else sig.length) > 8:
        raise cv.Invalid(f"{path}: {name}: field reaches past byte 7")
    if sig.on is not None and sig.on not in [v for _, v in sig.values]:
        raise cv.Invalid(f"{path}: {name}: 'on' must be one of the values")
    return sig


def _title(path, data):
    v = data.get("vehicle", {})
    title = " ".join(str(x) for x in (v.get("make"), v.get("model"), v.get("generation")) if x) or path.stem
    years = v.get("model_years") or []
    if years:
        title += f" ({min(years)})" if min(years) == max(years) else f" ({min(years)}-{max(years)})"
    return title


_profiles = None


def load_profiles():
    """All profiles from <config dir>/vehicles, sorted by file name (cached for the run)."""
    global _profiles
    if _profiles is None:
        folder = Path(CORE.relative_config_path(PROFILE_DIR))
        found = []
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("schema") != 1:
                raise cv.Invalid(f"{path}: unsupported profile schema {data.get('schema')}")
            found.append(Profile(path.stem, _title(path, data), [_parse_signal(path, s) for s in data.get("signals", [])]))
        _profiles = found
    return _profiles


def signal_catalog():
    """name -> first Signal seen with that name; the same name must have the same kind in every profile."""
    catalog = {}
    for p in load_profiles():
        for s in p.signals:
            known = catalog.setdefault(s.name, s)
            if known.kind != s.kind:
                raise cv.Invalid(f"signal {s.name} is a {known.kind} in one profile and a {s.kind} in {p.id}")
    return catalog


def signal_index(name):
    return list(signal_catalog()).index(name)


def signals_validator(platform, allowed, make_schema):
    """Validator for a `signals:` map {signal name: entity config} of one entity platform."""

    def validate(value):
        if not isinstance(value, dict):
            raise cv.Invalid("signals: expected a map of signal name -> entity")
        catalog = signal_catalog()
        if not catalog:
            raise cv.Invalid(f"no vehicle profiles found in '{CORE.relative_config_path(PROFILE_DIR)}' "
                             "(copy firmware/vehicles next to the YAML)")
        schema = {}
        for name in value:
            sig = catalog.get(name)
            if sig is None:
                raise cv.Invalid(f"unknown signal '{name}', the profiles have: {', '.join(catalog)}", [name])
            if not allowed(sig):
                raise cv.Invalid(f"signal '{name}' is a {sig.kind} and can't be a {platform}", [name])
            schema[cv.Optional(str(name))] = make_schema(str(name), sig)
        return cv.Schema(schema)({str(k): v or {} for k, v in value.items()})

    return validate
