"""Locate the KiCad 10 installation without hard-coding machine-specific paths.

Order: $KICAD_DIR (the KiCad install root, containing bin/ and share/), kicad-cli on PATH,
then the default install locations for Windows, macOS and Linux.
"""
import os
import shutil
import sys
from pathlib import Path

VERSION = '10.0'


def _candidates():
    if os.environ.get('KICAD_DIR'):
        yield Path(os.environ['KICAD_DIR'])
    cli = shutil.which('kicad-cli')
    if cli:
        yield Path(cli).resolve().parent.parent
    if sys.platform == 'win32':
        for var in ('ProgramFiles', 'LOCALAPPDATA'):
            base = os.environ.get(var)
            if base:
                yield Path(base) / 'KiCad' / VERSION
                yield Path(base) / 'Programs' / 'KiCad' / VERSION
    elif sys.platform == 'darwin':
        yield Path('/Applications/KiCad/KiCad.app/Contents')
    else:
        yield Path('/usr')
        yield Path('/usr/local')


def _find():
    exe = 'kicad-cli.exe' if sys.platform == 'win32' else 'kicad-cli'
    for root in _candidates():
        for b in (root / 'bin', root / 'MacOS'):
            if (b / exe).exists():
                return root, b / exe
    raise SystemExit('KiCad 10 not found: set KICAD_DIR to the KiCad install folder (containing bin/ and share/)')


ROOT, CLI = _find()


def share(*parts):
    """path inside KiCad's shared data (symbols, footprints, ...)"""
    for base in (ROOT / 'share' / 'kicad', ROOT / 'SharedSupport', Path('/usr/share/kicad')):
        if base.exists():
            return base.joinpath(*parts)
    return ROOT.joinpath('share', 'kicad', *parts)


SYMBOLS = share('symbols')
FOOTPRINTS = share('footprints')
