"""Render the demo report to docs/preview.png and refresh the README example.

Run from the repo root:  python docs/render_preview.py  (dev only, needs Pillow)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BACKGROUND = "#0f172a"
FOREGROUND = "#e2e8f0"
ACCENT = "#38bdf8"
PADDING = 28
LINE_HEIGHT = 26
FONT_SIZE = 17
EXAMPLE_HEADING = "## Example report"
FENCE = "```text\n"


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSansMono.ttf", "Consolas.ttf", "Menlo.ttc"):
        try:
            return ImageFont.truetype(name, FONT_SIZE)
        except OSError:
            continue
    return ImageFont.load_default(size=FONT_SIZE)


def render(text: str, out: Path) -> None:
    font = _font()
    lines = text.splitlines() or [""]
    widest = max(font.getlength(line) for line in lines)
    width = PADDING * 2 + int(widest) + PADDING
    height = PADDING * 2 + LINE_HEIGHT * len(lines)
    image = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width - 1, 6], fill=ACCENT)
    for index, line in enumerate(lines):
        draw.text((PADDING, PADDING + index * LINE_HEIGHT), line, font=font, fill=FOREGROUND)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="PNG", optimize=True)


def refresh_readme(text: str, path: Path) -> bool:
    """Replace the fenced example block under the README example heading."""
    original = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    content = original.decode("utf-8").replace("\r\n", "\n")
    head, heading, tail = content.partition(EXAMPLE_HEADING)
    if not heading:
        return False
    before, fence, after = tail.partition(FENCE)
    if not fence:
        return False
    _, closing, rest = after.partition("\n```")
    if not closing:
        return False
    updated = head + heading + before + fence + text + closing + rest
    encoded = updated.encode("utf-8").replace(b"\n", newline)
    if encoded != original:
        path.write_bytes(encoded)
    return True


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from clvreport.report import analyze, format_text
    from clvreport.simulate import simulate_bets

    text = format_text(analyze(simulate_bets(40_000, seed=1), seed=0, resamples=1000))
    out = ROOT / "docs" / "preview.png"
    render(text, out)
    readme = ROOT / "README.md"
    refreshed = refresh_readme(text, readme)
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    state = "refreshed" if refreshed else "left unchanged"
    print(f"{state} the {readme.name} example block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
