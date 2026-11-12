"""Prepare a firmware release for the dongle's update-over-LTE (ESPHome http_request update).

    python firmware/tools/make_release.py <obd-v2x-dongle.ota.bin> <out dir> [--version X.Y.Z] [--summary TEXT]

<ota.bin>: the "OTA" image (ESPHome Builder: Download -> OTA format, or .esphome/build/<name>/.pioenvs/<name>/
firmware.ota.bin after `esphome compile`). Writes <out dir>/firmware.ota.bin and <out dir>/manifest.json; copy both
to the web server directory that `ota_manifest_url` in secrets.yaml points to. The version defaults to
esphome.project.version in obd-v2x-dongle.yaml and must differ from the installed one, or the dongle sees no update.
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil

FW_DIR = pathlib.Path(__file__).resolve().parent.parent


def project_version():
    text = (FW_DIR / 'obd-v2x-dongle.yaml').read_text(encoding='utf-8')
    m = re.search(r'^\s+version:\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit('esphome.project.version not found in obd-v2x-dongle.yaml')
    return m.group(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bin', type=pathlib.Path)
    ap.add_argument('out', type=pathlib.Path)
    ap.add_argument('--version')
    ap.add_argument('--summary', default='')
    a = ap.parse_args()

    data = a.bin.read_bytes()
    if data[:1] != b'\xe9':
        raise SystemExit(f'{a.bin} is not an ESP32 app image (use the OTA .bin, not the factory image)')
    a.out.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.bin, a.out / 'firmware.ota.bin')
    version = a.version or project_version()
    ota = {'path': 'firmware.ota.bin', 'md5': hashlib.md5(data).hexdigest()}
    if a.summary:
        ota['summary'] = a.summary
    manifest = {
        'name': 'obd-v2x-dongle',
        'version': version,
        'builds': [{'chipFamily': 'ESP32-C5', 'ota': ota}],
    }
    (a.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'version {version}, {len(data)} bytes, md5 {ota["md5"]} -> {a.out}')


if __name__ == '__main__':
    main()
