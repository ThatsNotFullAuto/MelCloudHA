"""Render an original vector emblem to HA's local brand image sizes.

Cyan house = home automation; red three-diamond motif = Mitsubishi equipment;
the pulse = diagnostics. No Home Assistant logo asset is copied.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "custom_components/melcloud_diagnostics/brand"
OUT.mkdir(parents=True, exist_ok=True)
CYAN = "#00A9CE"
RED = "#E52235"


def diamonds():
    for angle in (0, 120, 240):
        theta = math.radians(angle)
        points = []
        for x, y in [(0, -4), (-18, -36), (0, -68), (18, -36)]:
            points.append(
                (
                    128 + x * math.cos(theta) - y * math.sin(theta),
                    134 + x * math.sin(theta) + y * math.cos(theta),
                )
            )
        yield points


def icon(size):
    # Draw the same vector geometry at 4x target size for clean small-size edges.
    scale = size * 4 / 256
    img = Image.new("RGBA", (size * 4, size * 4))
    draw = ImageDraw.Draw(img)

    def line(points, width, color=CYAN):
        pts = [(x * scale, y * scale) for x, y in points]
        draw.line(pts, fill=color, width=round(width * scale), joint="curve")
        radius = width * scale / 2
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

    line([(14, 107), (128, 14), (242, 107)], 20)
    line([(38, 112), (38, 242), (218, 242), (218, 112)], 17)
    for polygon in diamonds():
        draw.polygon([(x * scale, y * scale) for x, y in polygon], fill=RED)
    line([(76, 201), (101, 201), (115, 181), (132, 219), (147, 201), (180, 201)], 9)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def font(size, bold=False):
    fonts = Path("C:/Windows/Fonts")
    return ImageFont.truetype(str(fonts / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)


for factor, suffix in [(1, ""), (2, "@2x")]:
    image = icon(256 * factor)
    for prefix in ("", "dark_"):
        image.save(OUT / f"{prefix}icon{suffix}.png", optimize=True)
        logo = Image.new("RGBA", (1120 * factor, 256 * factor))
        logo.alpha_composite(image)
        draw = ImageDraw.Draw(logo)
        fg = "#EDF6FF" if prefix else "#162C40"
        draw.text(
            (288 * factor, 44 * factor),
            "MELCloud Diagnostics",
            font=font(65 * factor, True),
            fill=fg,
        )
        draw.text(
            (292 * factor, 145 * factor),
            "ECODAN / HOME ASSISTANT",
            font=font(31 * factor),
            fill=CYAN,
        )
        # Crop text canvas to the actual subject, retaining standard icon height.
        logo.crop((0, 0, logo.getbbox()[2], 256 * factor)).save(
            OUT / f"{prefix}logo{suffix}.png", optimize=True
        )

polygons = "".join(
    '<polygon points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in p) + '"/>' for p in diamonds()
)
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" role="img" aria-label="MELCloud Diagnostics: casa, tre diamanti e segnale diagnostico">
<g fill="none" stroke="{CYAN}" stroke-linecap="round" stroke-linejoin="round"><path d="M14 107 128 14 242 107" stroke-width="20"/><path d="M38 112V242H218V112" stroke-width="17"/></g>
<g fill="{RED}">{polygons}</g><path d="M76 201H101L115 181 132 219 147 201H180" fill="none" stroke="{CYAN}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
</svg>'''
(OUT / "icon.svg").write_text(svg, encoding="utf-8")
print(f"Brand images generated in {OUT}")
