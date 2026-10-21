"""Prep the source photo for ASCII conversion.

A flatly-lit face converts to a dark, unreadable blob. Three steps fix that:
  1. Remove the background with rembg so the subject is isolated.
  2. Boost local contrast with OpenCV's CLAHE (contrast-limited adaptive
     histogram equalization) -- this gives a flat face real highlights and shadows.
  3. Composite onto pure white so the background maps to the blank end of
     the ASCII ramp (white -> spaces).

Run once per photo:  python scripts/prep_photo.py source-photo.png
Output:             scripts/source-prepped.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session, remove

HERE = Path(__file__).resolve().parent

# Pin the classic u2net model: it ships with a small cached download, while this
# rembg version's default (bria-rmbg) pulls a 1GB model. The daily workflow
# never re-runs this step, so the choice only affects local one-off prep runs.
SESSION = new_session("u2net")


def prep(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGB")

    # 1. Isolate the subject with the pinned u2net session (see SESSION above).
    #    Passing session= is required: remove() silently ignores session_name
    #    and would otherwise spin up the default bria-rmbg session (~1GB).
    cutout = remove(img, session=SESSION)  # RGBA
    print(f"[prep] background removed -> {cutout.size}")

    # 2. CLAHE on the luminance channel only, so colors stay natural.
    bgra = cv2.cvtColor(np.array(cutout), cv2.COLOR_RGBA2BGRA)
    lab = cv2.cvtColor(bgra, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    print("[prep] CLAHE contrast boost applied")

    # 3. Composite over white so the background maps to the blank end of the ramp.
    alpha = bgra[:, :, 3:4].astype(np.float32) / 255.0
    white = np.full_like(enhanced, 255, dtype=np.uint8)
    composited = (enhanced.astype(np.float32) * alpha + white.astype(np.float32) * (1 - alpha)).astype(np.uint8)

    gray = cv2.cvtColor(composited, cv2.COLOR_BGR2GRAY)
    print(f"[prep] grayscale range: min={gray.min()} max={gray.max()} mean={gray.mean():.1f}")

    cv2.imwrite(str(dst), gray)
    print(f"[prep] wrote {dst}")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "source-photo.png"
    dst = HERE / "source-prepped.png"
    if not src.exists():
        sys.exit(f"photo not found: {src}")
    prep(src, dst)
