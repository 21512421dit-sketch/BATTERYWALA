"""Extract inline prototype images into cacheable static files.

The source prototype stays untouched. Running this script creates a compact HTML
copy that is much faster to deliver over a public tunnel.
"""

import base64
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "original_main_prototype.html"
OUTPUT = ROOT / "docs" / "optimized_main_prototype.html"
ASSET_DIR = ROOT / "app" / "static" / "prototype-assets"
DATA_URI = re.compile(r"data:image/(?P<kind>png|jpeg|jpg|webp);base64,(?P<data>[A-Za-z0-9+/=]+)")


def extract(match: re.Match[str]) -> str:
    raw = base64.b64decode(match.group("data"))
    digest = hashlib.sha256(raw).hexdigest()[:20]
    extension = "jpg" if match.group("kind") in {"jpeg", "jpg"} else match.group("kind")
    target = ASSET_DIR / f"{digest}.{extension}"
    if not target.exists():
        target.write_bytes(raw)
    return f"/static/prototype-assets/{target.name}"


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text(encoding="utf-8")
    optimized, replacements = DATA_URI.subn(extract, source)
    forklift_start = optimized.index(
        '<div class="slide"><img alt="Amaron heavy duty automotive battery in a mobility setting"'
    )
    next_slide = optimized.index(
        '<div class="slide"><img alt="Battery technician installing a vehicle battery"',
        forklift_start,
    )
    forklift_slide = optimized[forklift_start:next_slide]
    optimized = optimized[:next_slide] + forklift_slide + optimized[next_slide:]
    slide_five_dot = '<button aria-label="Slide 5" class="dot" type="button"></button>'
    optimized = optimized.replace(
        slide_five_dot,
        slide_five_dot + '<button aria-label="Slide 6" class="dot" type="button"></button>',
        1,
    )
    OUTPUT.write_text(optimized, encoding="utf-8")
    print(f"Extracted {replacements} inline image references into {ASSET_DIR}")
    print(f"Optimized HTML: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
