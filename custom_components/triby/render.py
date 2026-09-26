"""Render text and images into the 296x128 PNG the Triby displays (blocking; run in executor)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from .api import HEIGHT, WIDTH

MARGIN = 7


def _wrap(text: str, font: ImageFont.FreeTypeFont) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        cur = ""
        for word in paragraph.split():
            trial = f"{cur} {word}".strip()
            if not cur or font.getlength(trial) <= WIDTH - 2 * MARGIN:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def render_text(text: str) -> Image.Image:
    """Black text on transparent background, using the largest font size that fits."""
    for size in range(64, 9, -2):
        font = ImageFont.load_default(size)  # Pillow's bundled scalable font
        lines = _wrap(text, font)
        line_h = int(size * 1.15)
        if len(lines) * line_h <= HEIGHT - 2 * MARGIN and all(
            font.getlength(line) <= WIDTH - 2 * MARGIN for line in lines
        ):
            break
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = (HEIGHT - len(lines) * line_h) // 2
    for line in lines:
        # 1px stroke fakes a bold weight, which reads better on e-ink
        draw.text(((WIDTH - font.getlength(line)) / 2, y), line, font=font, fill=(0, 0, 0, 255),
                  stroke_width=1, stroke_fill=(0, 0, 0, 255))
        y += line_h
    return img


def render_image(data: bytes) -> Image.Image:
    """Fit an arbitrary image onto the canvas, dithered to black/transparent (e-ink)."""
    src = Image.open(io.BytesIO(data))
    if src.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGBA", src.size, (255, 255, 255, 255))
        src = Image.alpha_composite(bg, src.convert("RGBA"))
    src = src.convert("L")
    src.thumbnail((WIDTH, HEIGHT))
    bw = src.convert("1")  # Floyd-Steinberg dither
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ink = Image.new("RGBA", bw.size, (0, 0, 0, 255))
    img.paste(ink, ((WIDTH - bw.width) // 2, (HEIGHT - bw.height) // 2), bw.point(lambda p: 255 - p))
    return img


def to_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def build_png(message: str | None, title: str | None = None, image: bytes | None = None) -> bytes:
    """Image wins if given; otherwise title and message are rendered as text."""
    if image is not None:
        return to_png(render_image(image))
    text = "\n".join(part for part in (title, message) if part)
    return to_png(render_text(text))
