#!/usr/bin/env python3
"""Generate the 1200x630 OG image for the Citation Monitor landing page.

Palette matches the store aesthetic (dark-mode palette as the base).
Run: python3 scripts/make_og_image.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "og-image.png"

W, H = 1200, 630
INK = (226, 232, 240)
MUTED = (159, 176, 208)
ACCENT = (138, 180, 255)
GOOD = (52, 211, 153)
LINE = (36, 51, 80)
SURFACE = (17, 26, 46)
BG = (11, 18, 32)

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
LEFT = 80


def font(name: str, size: int):
    return ImageFont.truetype(FONT_DIR + name, size)


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 6], fill=ACCENT)

    d.text((LEFT, 56), "Citation Monitor", font=font("DejaVuSans-Bold.ttf", 34), fill=INK)
    d.text((LEFT, 106), "Xion's Micro Tools · weekly AI citation digest",
           font=font("DejaVuSans.ttf", 23), fill=MUTED)

    # headline — three lines, measured to fit within W - 2*LEFT
    f_head = font("DejaVuSans-Bold.ttf", 56)
    for i, line in enumerate(("Know whether AI engines",
                              "recommend you —",
                              "or your competitors.")):
        assert d.textlength(line, font=f_head) <= W - 2 * LEFT, line
        d.text((LEFT, 162 + i * 68), line, font=f_head, fill=INK)

    d.text((LEFT, 386), "36 real buyer questions · real engine answers · exactly 3 fixes / week",
           font=font("DejaVuSans.ttf", 25), fill=MUTED)

    # stat chips (real baseline numbers from the live sample digest)
    chips = [
        ("0 / 72", "brand citations", GOOD),
        ("25", "BitPay citations", ACCENT),
        ("3", "fixes every Monday", ACCENT),
    ]
    f_val = font("DejaVuSans-Bold.ttf", 36)
    f_lab = font("DejaVuSans.ttf", 20)
    x, y, ch_h = LEFT, 444, 92
    for value, label, color in chips:
        box_w = max(d.textlength(value, font=f_val), d.textlength(label, font=f_lab)) + 44
        d.rounded_rectangle([x, y, x + box_w, y + ch_h], radius=16, fill=SURFACE, outline=LINE, width=2)
        d.text((x + 20, y + 12), value, font=f_val, fill=color)
        d.text((x + 20, y + 58), label, font=f_lab, fill=MUTED)
        x += box_w + 20
    assert x <= W, "chips overflow"

    d.text((LEFT, 570), "pay in BTC / ETH / SOL — no card needed",
           font=font("DejaVuSans.ttf", 21), fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
