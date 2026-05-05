from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "agent-council-demo.gif"

WIDTH = 1400
HEIGHT = 900
PADDING = 32
LINE_HEIGHT = 30
FONT_SIZE = 22
BG = "#1e1f29"
FG = "#f8f8f2"
DIM = "#8b8fa3"
GREEN = "#50fa7b"
CYAN = "#8be9fd"
PINK = "#ff79c6"
YELLOW = "#f1fa8c"


TRANSCRIPT = [
    ("cmd", "$ python -m agent_council ask Should-we-add-Redis-caching? --config demo/agents.yaml --providers claude-mock,codex-mock,gemini-mock --quiet"),
    ("out", "------------------------------------------------------------------------"),
    ("out", "session ask-20260505-121423-3c7618  workers=3"),
    ("agent", "claude-mock:"),
    ("out", "  Recommendation: add Redis only after measuring the slow path."),
    ("out", "  Redis is a good fit for shared rate-limit counters and hot read-heavy objects,"),
    ("out", "  but it should not become the source of truth."),
    ("agent", "codex-mock:"),
    ("out", "  Recommendation: do not add Redis yet."),
    ("out", "  First add timing, query metrics, and tests around cache expiry and outage behavior."),
    ("agent", "gemini-mock:"),
    ("out", "  Recommendation: use Redis for rate limiting, not broad response caching."),
    ("out", "  Start narrow, add observability, and keep a kill switch."),
    ("out", "------------------------------------------------------------------------"),
    ("blank", ""),
    ("cmd", "$ python -m agent_council memory-candidates --project agent-council-cli --format jsonl | head -n 2"),
    ("json", '{"source_agent":"claude-mock","target_namespace":"agent:claude-mock","memory_type":"architecture","confidence":0.75,"status":"candidate"}'),
    ("json", '{"source_agent":"claude-mock","target_namespace":"project:agent-council-cli","memory_type":"architecture","confidence":0.65,"status":"candidate"}'),
]


def font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, FONT_SIZE)
    return ImageFont.load_default()


def color(kind: str) -> str:
    return {
        "cmd": GREEN,
        "agent": CYAN,
        "json": YELLOW,
        "blank": FG,
    }.get(kind, FG)


def wrapped_lines(lines: list[tuple[str, str]]) -> list[tuple[str, str]]:
    rendered: list[tuple[str, str]] = []
    for kind, text in lines:
        if not text:
            rendered.append((kind, ""))
            continue
        width = 96 if kind == "json" else 100
        parts = wrap(text, width=width, replace_whitespace=False) or [text]
        for i, part in enumerate(parts):
            rendered.append((kind if i == 0 else "out", part))
    return rendered


def make_frame(visible_count: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    mono = font()

    draw.rounded_rectangle(
        (16, 16, WIDTH - 16, HEIGHT - 16),
        radius=18,
        fill="#282a36",
        outline="#44475a",
        width=2,
    )
    draw.ellipse((42, 40, 58, 56), fill="#ff5555")
    draw.ellipse((68, 40, 84, 56), fill="#f1fa8c")
    draw.ellipse((94, 40, 110, 56), fill="#50fa7b")
    draw.text((PADDING, 78), "agent-council-cli demo", font=mono, fill=PINK)
    draw.text((PADDING, 110), "same prompt -> multiple AI CLIs -> comparison + memory candidates", font=mono, fill=DIM)

    y = 158
    for kind, text in wrapped_lines(TRANSCRIPT[:visible_count]):
        draw.text((PADDING, y), text, font=mono, fill=color(kind))
        y += LINE_HEIGHT
        if y > HEIGHT - PADDING - LINE_HEIGHT:
            break
    return image


def main() -> int:
    frames: list[Image.Image] = []
    for visible_count in range(1, len(TRANSCRIPT) + 1):
        frames.append(make_frame(visible_count))
    frames.extend([make_frame(len(TRANSCRIPT))] * 8)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=420,
        loop=0,
        optimize=True,
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
