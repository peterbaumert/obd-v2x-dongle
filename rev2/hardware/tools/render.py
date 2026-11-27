"""3D renders of both rev 2 boards for the READMEs (system Python with Pillow; finds kicad-cli via kicad_env).

    python rev2/hardware/tools/render.py

Writes rev2/docs/img/: <board>-top.png, <board>-bottom.png (straight views) and <board>-iso.png (isometric), with a
transparent background cropped to the board. Re-run after board changes.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import kicad_env  # noqa: E402

HW = Path(__file__).resolve().parents[1]
IMG = HW.parent / 'docs' / 'img'
VIEWS = {                       # name: kicad-cli arguments
    'top': ['--side', 'top', '--zoom', '0.9', '--quality', 'basic'],
    'bottom': ['--side', 'bottom', '--zoom', '0.9', '--quality', 'basic'],
    'iso': ['--side', 'top', '--rotate', '-50,0,35', '--zoom', '0.6', '--quality', 'high'],
}


def render(board, view, args):
    out = IMG / f'{board}-{view}.png'
    subprocess.run([str(kicad_env.CLI), 'pcb', 'render', '-o', str(out), '-w', '1800', '-h', '1800',
                    '--background', 'transparent', *args,
                    str(HW / board / f'obd-v2x-{board}.kicad_pcb')], check=True, stdout=subprocess.DEVNULL)
    im = Image.open(out)
    box = im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        pad = 12
        im = im.crop((max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, im.width), min(box[3] + pad, im.height)))
    im.thumbnail((900, 900))
    im.save(out, optimize=True)
    print(out.relative_to(HW.parents[1]), im.size)


def main():
    IMG.mkdir(parents=True, exist_ok=True)
    for board in ('carrier', 'upper'):
        for view, args in VIEWS.items():
            render(board, view, args)


if __name__ == '__main__':
    main()
