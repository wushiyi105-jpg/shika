"""把原图压成 samples/card-1.jpg（1200px 宽、质量 82）。

样例图本来就是生成出来的，压一下只是为了让仓库轻一点。
    python scripts/shrink_sample.py data/test-card.jpg samples/card-1.jpg
"""

from __future__ import annotations

import os
import sys

from PIL import Image


def main(src: str, dst: str, width: int = 1200, quality: int = 82) -> None:
    img = Image.open(src).convert("RGB")
    if img.width > width:
        h = int(img.height * width / img.width)
        img = img.resize((width, h), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    img.save(dst, format="JPEG", quality=quality, optimize=True)
    print(f"ok -> {dst}  {img.width}×{img.height}  {os.path.getsize(dst) / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
